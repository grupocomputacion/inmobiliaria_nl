import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, date, timedelta
import urllib.parse
import io

# --- 1. CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Inmobiliaria Pro Cloud", layout="wide", initial_sidebar_state="expanded")

# --- 2. FUNCIONES DE MOTOR Y FORMATEO ---
def conectar():
    return sqlite3.connect('datos_alquileres.db', check_same_thread=False)

def fmt_moneda(valor):
    try:
        return f"$ {int(float(valor or 0)):,}".replace(",", ".")
    except:
        return "$ 0"

def crear_link_whatsapp(tel, mensaje):
    tel_limpio = "".join(filter(str.isdigit, str(tel)))
    texto = urllib.parse.quote(mensaje)
    return f"https://wa.me/{tel_limpio}?text={texto}"

def init_db():
    """Inicialización con reparación automática de columnas"""
    conn = conectar()
    c = conn.cursor()
    # Tablas Base
    c.execute("CREATE TABLE IF NOT EXISTS bloques (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT UNIQUE)")
    c.execute("CREATE TABLE IF NOT EXISTS inmuebles (id INTEGER PRIMARY KEY AUTOINCREMENT, id_bloque INTEGER, tipo TEXT, precio_alquiler REAL, costo_contrato REAL, deposito_base REAL, estado TEXT DEFAULT 'Libre')")
    c.execute("CREATE TABLE IF NOT EXISTS inquilinos (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT, celular TEXT, procedencia TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS contratos (id INTEGER PRIMARY KEY AUTOINCREMENT, id_inmueble INTEGER, id_inquilino INTEGER, fecha_inicio DATE, meses INTEGER)")
    c.execute("CREATE TABLE IF NOT EXISTS deudas (id INTEGER PRIMARY KEY AUTOINCREMENT, id_contrato INTEGER, concepto TEXT, mes_anio TEXT, monto_debe REAL, monto_pago REAL DEFAULT 0, pagado INTEGER DEFAULT 0, fecha_cobro DATE)")
    
    # REPARACIÓN: Agregamos columnas faltantes una por una
    columnas_nuevas = [
        ("fecha_fin", "DATE"), 
        ("activo", "INTEGER DEFAULT 1"), 
        ("monto_alquiler", "REAL DEFAULT 0"),
        ("monto_contrato", "REAL DEFAULT 0"),
        ("monto_deposito", "REAL DEFAULT 0")
    ]
    for col, tipo in columnas_nuevas:
        try:
            c.execute(f"ALTER TABLE contratos ADD COLUMN {col} {tipo}")
        except sqlite3.OperationalError:
            pass # Ya existe
            
    conn.commit()
    conn.close()

def inicializar_absoluto():
    conn = conectar()
    c = conn.cursor()
    for t in ["deudas", "contratos", "inquilinos", "inmuebles", "bloques"]:
        c.execute(f"DROP TABLE IF EXISTS {t}")
    conn.commit()
    conn.close()
    init_db()

# Ejecutar siempre al inicio
init_db()

# --- 3. MENÚ LATERAL ---
with st.sidebar:
    st.title("🏢 Inmobiliaria Pro")
    if st.button("🚨 REINICIAR TODA LA BASE"):
        inicializar_absoluto()
        st.cache_data.clear()
        st.rerun()
    
    st.divider()
    menu = st.radio(
        "Navegación:",
        ["🏠 1. Inventario", "📝 2. Nuevo Contrato", "💰 3. Cobranzas", "🚨 4. Morosos", "📊 5. Caja", "⚙️ 6. Configuración"],
        label_visibility="collapsed"
    )

# ---------------------------------------------------------
# 1. INVENTARIO (PROTEGIDO CONTRA ERRORES DE COLUMNA)
# ---------------------------------------------------------
if menu == "🏠 1. Inventario":
    st.subheader("Estado de Unidades y Disponibilidad")
    conn = conectar()
    hoy = date.today()
    
    query = """
        SELECT 
            i.id, b.nombre as Bloque, i.tipo as Unidad, 
            i.precio_alquiler, i.costo_contrato, i.deposito_base,
            c.fecha_inicio, c.fecha_fin, c.activo
        FROM inmuebles i
        JOIN bloques b ON i.id_bloque = b.id
        LEFT JOIN contratos c ON i.id = c.id_inmueble AND c.activo = 1
        GROUP BY i.id 
    """
    try:
        df = pd.read_sql_query(query, conn)

        def calcular_sit(row):
            if pd.isna(row['fecha_inicio']) or row['activo'] == 0: return "Libre", "LIBRE HOY"
            try:
                f_ini = pd.to_datetime(row['fecha_inicio']).date()
                f_fin = pd.to_datetime(row['fecha_fin']).date()
                if hoy < f_ini: return "RESERVADO", f_ini.strftime('%d/%m/%Y')
                elif hoy <= f_fin: return "OCUPADO", f_fin.strftime('%d/%m/%Y')
                else: return "VENCIDO", "LIBRE HOY"
            except: return "Libre", "LIBRE HOY"

        if not df.empty:
            df[['Situación', 'Disponible Desde']] = df.apply(lambda x: pd.Series(calcular_sit(x)), axis=1)
            df['Alquiler'] = df['precio_alquiler'].apply(fmt_moneda)
            df['Contrato'] = df['costo_contrato'].apply(fmt_moneda)
            df['Depósito'] = df['deposito_base'].apply(fmt_moneda)
            
            def color_sit(val):
                if val == "Libre": color = '#28a745'
                elif val == "OCUPADO": color = '#dc3545'
                else: color = '#fd7e14'
                return f'color: {color}; font-weight: bold'

            cols = ["Bloque", "Unidad", "Situación", "Disponible Desde", "Alquiler", "Contrato", "Depósito"]
            st.dataframe(df[cols].style.applymap(color_sit, subset=['Situación']), use_container_width=True, hide_index=True)
        else:
            st.info("Sin unidades. Cargue datos en Configuración.")
    except Exception as e:
        st.error(f"Error detectado: {e}")
        st.info("Intente pulsar el botón de REINICIAR en la barra lateral.")

# ---------------------------------------------------------
# 2. NUEVO CONTRATO (SUGERENCIA AUTOMÁTICA)
# ---------------------------------------------------------
elif menu == "📝 2. Nuevo Contrato":
    st.subheader("Alta de Alquiler")
    conn = conectar()
    inm_db = pd.read_sql_query("SELECT id, tipo, precio_alquiler, costo_contrato, deposito_base FROM inmuebles", conn)
    inq_db = pd.read_sql_query("SELECT id, nombre FROM inquilinos", conn)
    
    if not inm_db.empty and not inq_db.empty:
        with st.form("f_con"):
            c1, c2 = st.columns(2)
            id_inm = c1.selectbox("Unidad", inm_db['id'].tolist(), format_func=lambda x: f"{inm_db[inm_db['id']==x]['tipo'].values[0]}")
            id_inq = c2.selectbox("Inquilino", inq_db['id'].tolist(), format_func=lambda x: inq_db[inq_db['id']==x]['nombre'].values[0])
            
            f_ini = c1.date_input("Fecha Inicio", date.today())
            meses = c2.number_input("Meses", min_value=1, value=6)
            f_fin = f_ini + timedelta(days=meses * 30)
            
            val_ref = inm_db[inm_db['id'] == id_inm].iloc[0]
            m_alq = c1.number_input("Monto Alquiler", value=float(val_ref['precio_alquiler']))
            m_con = c2.number_input("Costo Contrato", value=float(val_ref['costo_contrato']))
            m_dep = c1.number_input("Depósito", value=float(val_ref['deposito_base']))

            if st.form_submit_button("Grabar Contrato"):
                cur = conn.cursor()
                cur.execute("""INSERT INTO contratos (id_inmueble, id_inquilino, fecha_inicio, fecha_fin, meses, activo, monto_alquiler, monto_contrato, monto_deposito) 
                               VALUES (?,?,?,?,?,1,?,?,?)""", (id_inm, id_inq, f_ini, f_fin, meses, m_alq, m_con, m_dep))
                conn.commit(); st.success("Contrato grabado"); st.rerun()
    else: st.warning("Cargue unidades e inquilinos primero.")

# ---------------------------------------------------------
# 3. COBRANZAS (WHATSAPP + SALDO)
# ---------------------------------------------------------
elif menu == "💰 3. Cobranzas":
    st.subheader("Cobros y Recibos")
    conn = conectar()
    df_c = pd.read_sql_query("""
        SELECT d.id, i.tipo, inq.nombre, d.monto_debe, d.monto_pago, inq.celular, d.concepto
        FROM deudas d JOIN contratos c ON d.id_contrato=c.id
        JOIN inmuebles i ON c.id_inmueble=i.id JOIN inquilinos inq ON c.id_inquilino=inq.id
        WHERE d.pagado = 0
    """, conn)
    
    for _, row in df_c.iterrows():
        with st.expander(f"{row['tipo']} - {row['nombre']} ({row['concepto']})"):
            saldo = row['monto_debe'] - row['monto_pago']
            st.write(f"Saldo Pendiente: **{fmt_moneda(saldo)}**")
            pago = st.number_input("Monto a cobrar", min_value=0.0, max_value=float(saldo), key=f"c_{row['id']}")
            if st.button("Confirmar Pago", key=f"b_{row['id']}"):
                nuevo = row['monto_pago'] + pago
                pagado = 1 if nuevo >= row['monto_debe'] else 0
                conn.execute("UPDATE deudas SET monto_pago=?, pagado=?, fecha_cobro=? WHERE id=?", (nuevo, pagado, date.today(), row['id']))
                conn.commit()
                msg = f"✅ *RECIBO*\\nUnidad: {row['tipo']}\\nAbonado: {fmt_moneda(pago)}\\nSaldo: {fmt_moneda(saldo-pago)}"
                st.session_state[f'wa_{row["id"]}'] = crear_link_whatsapp(row['celular'], msg)
                st.rerun()
            if f'wa_{row["id"]}' in st.session_state:
                st.markdown(f'<a href="{st.session_state[f"wa_{row[id]}"]}" target="_blank"><button style="background-color:#25D366; color:white; border:none; padding:12px; border-radius:8px; width:100%; cursor:pointer; font-weight:bold;">📲 Enviar por WhatsApp</button></a>', unsafe_allow_html=True)

# ---------------------------------------------------------
# 4. MOROSOS, 5. CAJA Y 6. CONFIGURACIÓN (RESTAURADOS)
# ---------------------------------------------------------
elif menu == "🚨 4. Morosos":
    st.subheader("Deudores")
    conn = conectar()
    df_m = pd.read_sql_query("""SELECT inq.nombre as Inquilino, i.tipo as Unidad, (d.monto_debe - d.monto_pago) as Saldo FROM deudas d JOIN contratos c ON d.id_contrato=c.id JOIN inmuebles i ON c.id_inmueble=i.id JOIN inquilinos inq ON c.id_inquilino=inq.id WHERE d.pagado = 0""", conn)
    if not df_m.empty:
        st.error(f"Total Mora: {fmt_moneda(df_m['Saldo'].sum())}")
        df_m['Saldo'] = df_m['Saldo'].apply(fmt_moneda); st.table(df_m)
    else: st.success("Todo al día.")

elif menu == "📊 5. Caja":
    st.subheader("Ingresos")
    df_cj = pd.read_sql_query("SELECT fecha_cobro as Fecha, concepto as Detalle, monto_pago as Monto FROM deudas WHERE pagado=1", conectar())
    if not df_cj.empty:
        st.metric("Total Recaudado", fmt_moneda(df_cj['Monto'].sum()))
        df_cj['Monto'] = df_cj['Monto'].apply(fmt_moneda); st.table(df_cj)

elif menu == "⚙️ 6. Configuración":
    st.subheader("Carga de Datos")
    t1, t2, t3, t4 = st.tabs(["👤 Inquilinos", "🏢 Bloques", "🏠 Unidades", "⚡ Procesos"])
    with t1:
        with st.form("f_inq"):
            c1, c2 = st.columns(2); nom = c1.text_input("Nombre"); tel = c2.text_input("Celular")
            if st.form_submit_button("Guardar"):
                con = conectar(); con.execute("INSERT INTO inquilinos (nombre, celular) VALUES (?,?)", (nom, tel)); con.commit(); st.success("Inquilino Creado")
    with t2:
        with st.form("f_blq"):
            nb = st.text_input("Nombre Bloque")
            if st.form_submit_button("Guardar"):
                con = conectar(); con.execute("INSERT INTO bloques (nombre) VALUES (?)", (nb,)); con.commit(); st.success("Bloque Creado")
    with t3:
        con = conectar(); bls = pd.read_sql_query("SELECT * FROM bloques", con)
        if not bls.empty:
            with st.form("f_inm"):
                idb = st.selectbox("Bloque", bls['id'].tolist(), format_func=lambda x: bls[bls['id']==x]['nombre'].values[0])
                tp = st.text_input("Unidad"); pr = st.number_input("Precio Alquiler", value=0.0); co = st.number_input("Costo Contrato", value=0.0); de = st.number_input("Depósito", value=0.0)
                if st.form_submit_button("Guardar"):
                    con.execute("INSERT INTO inmuebles (id_bloque, tipo, precio_alquiler, costo_contrato, deposito_base) VALUES (?,?,?,?,?)", (idb, tp, pr, co, de)); con.commit(); st.success("Unidad Creada"); st.rerun()
    with t4:
        st.write("### Generación Masiva")
        mes = st.text_input("Mes/Año (Ej: Mayo 2025)")
        if st.button("🚀 Generar Cuotas Mensuales"):
            con = conectar(); activos = pd.read_sql_query("SELECT id, monto_alquiler FROM contratos WHERE activo=1", con)
            for _, c in activos.iterrows():
                con.execute("INSERT INTO deudas (id_contrato, concepto, mes_anio, monto_debe) VALUES (?,?,?,?)", (c['id'], "Alquiler", mes, c['monto_alquiler']))
            con.commit(); st.success("Cuotas Generadas")
