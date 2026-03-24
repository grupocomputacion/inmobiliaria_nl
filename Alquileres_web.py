import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, date, timedelta
import io
import urllib.parse

# --- 1. CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Inmobiliaria Pro Cloud", layout="wide", initial_sidebar_state="expanded")

# --- 2. FUNCIONES DE MOTOR Y FORMATEO ---
def conectar():
    return sqlite3.connect('datos_alquileres.db', check_same_thread=False)

def fmt_moneda(valor):
    """Formatea importes: $ 1.250.000"""
    try:
        return f"$ {int(float(valor)):,}".replace(",", ".")
    except:
        return "$ 0"

def crear_link_whatsapp(tel, mensaje):
    texto = urllib.parse.quote(mensaje)
    return f"https://api.whatsapp.com/send?phone={tel}&text={texto}"

def inicializar_todo():
    """Borra y recrea todas las tablas para empezar de cero con la nueva lógica"""
    conn = conectar()
    c = conn.cursor()
    # Eliminar tablas anteriores para evitar DatabaseErrors
    c.execute("DROP TABLE IF EXISTS deudas")
    c.execute("DROP TABLE IF EXISTS contratos")
    c.execute("DROP TABLE IF EXISTS inquilinos")
    c.execute("DROP TABLE IF EXISTS inmuebles")
    c.execute("DROP TABLE IF EXISTS bloques")
    
    # Crear estructura nueva y profesional
    c.executescript('''
        CREATE TABLE bloques (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            nombre TEXT UNIQUE
        );
        CREATE TABLE inmuebles (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            id_bloque INTEGER, 
            tipo TEXT, 
            precio_alquiler REAL, 
            costo_contrato REAL, 
            deposito_base REAL, 
            estado TEXT DEFAULT 'Libre'
        );
        CREATE TABLE inquilinos (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            nombre TEXT, 
            celular TEXT, 
            procedencia TEXT, 
            grupo TEXT, 
            em_nombre TEXT, 
            em_tel TEXT
        );
        CREATE TABLE contratos (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            id_inmueble INTEGER, 
            id_inquilino INTEGER, 
            fecha_inicio DATE, 
            fecha_fin DATE, 
            meses INTEGER, 
            activo INTEGER DEFAULT 1, 
            monto_alquiler REAL
        );
        CREATE TABLE deudas (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            id_contrato INTEGER, 
            concepto TEXT, 
            mes_anio TEXT, 
            monto_debe REAL, 
            monto_pago REAL DEFAULT 0, 
            pagado INTEGER DEFAULT 0, 
            fecha_cobro DATE
        );
    ''')
    conn.commit()
    conn.close()

# --- BOTÓN DE REINICIO EN SIDEBAR (Solo para el Desarrollador) ---
with st.sidebar:
    st.title("🏢 Inmobiliaria Pro")
    if st.button("⚠️ REINICIALIZAR BASE DE DATOS"):
        inicializar_todo()
        st.success("Base de datos limpia y lista.")
    
    st.divider()
    menu = st.radio("Navegación:", 
                    ["🏠 Inventario", "📝 Nuevo Contrato", "💰 Cobranzas", "🚨 Morosos", "📊 Caja", "⚙️ Configuración"], 
                    label_visibility="collapsed")

# ---------------------------------------------------------
# MÓDULO 1: INVENTARIO CON SEMÁFORO Y DISPONIBILIDAD
# ---------------------------------------------------------
if menu == "🏠 Inventario":
    st.subheader("Estado de Unidades")
    conn = conectar()
    hoy = date.today()
    
    query = """
        SELECT i.id, b.nombre as Bloque, i.tipo as Unidad, i.precio_alquiler,
               c.fecha_inicio, c.fecha_fin, c.activo
        FROM inmuebles i
        JOIN bloques b ON i.id_bloque = b.id
        LEFT JOIN contratos c ON i.id = c.id_inmueble AND c.activo = 1
    """
    df = pd.read_sql_query(query, conn)

    def calcular_estado(row):
        if pd.isna(row['fecha_inicio']) or row['activo'] == 0: 
            return "Libre", "LIBRE HOY"
        try:
            f_ini = pd.to_datetime(row['fecha_inicio']).date()
            f_fin = pd.to_datetime(row['fecha_fin']).date()
            if hoy < f_ini: return "RESERVADO", f_ini.strftime('%d/%m/%Y')
            elif hoy <= f_fin: return "OCUPADO", f_fin.strftime('%d/%m/%Y')
            else: return "CONTRATO VENCIDO", "LIBRE HOY"
        except: return "Libre", "LIBRE HOY"

    if not df.empty:
        df[['Situación', 'Disponible Desde']] = df.apply(lambda x: pd.Series(calcular_estado(x)), axis=1)
        df['Alquiler'] = df['precio_alquiler'].apply(fmt_moneda)
        
        def color_sit(val):
            if val == "Libre": color = '#28a745' 
            elif val == "OCUPADO": color = '#dc3545' 
            elif val == "RESERVADO": color = '#007bff'
            else: color = '#fd7e14' 
            return f'color: {color}; font-weight: bold'

        st.dataframe(df[["Bloque", "Unidad", "Situación", "Disponible Desde", "Alquiler"]].style.applymap(color_sit, subset=['Situación']), 
                     use_container_width=True, hide_index=True)
    else:
        st.info("No hay unidades cargadas. Vaya a Configuración.")

# ---------------------------------------------------------
# MÓDULO 2: CONFIGURACIÓN (ALTA DE DATOS MAESTROS)
# ---------------------------------------------------------
elif menu == "⚙️ Configuración":
    st.subheader("Carga de Datos")
    t1, t2, t3, t4 = st.tabs(["👤 Inquilinos", "🏢 Bloques", "🏠 Unidades", "⚡ Procesos"])
    
    with t1:
        with st.form("f_inq"):
            c1, c2 = st.columns(2)
            nom = c1.text_input("Nombre Completo")
            tel = c2.text_input("Celular (549...)")
            if st.form_submit_button("Guardar Inquilino"):
                conn = conectar()
                conn.execute("INSERT INTO inquilinos (nombre, celular) VALUES (?,?)", (nom, tel))
                conn.commit(); st.success("Creado")

    with t2:
        with st.form("f_blq"):
            nom_b = st.text_input("Nombre del Bloque")
            if st.form_submit_button("Guardar Bloque"):
                conn = conectar(); conn.execute("INSERT INTO bloques (nombre) VALUES (?)", (nom_b,))
                conn.commit(); st.success("Bloque Creado")

    with t3:
        with st.form("f_inm"):
            conn = conectar()
            blqs = pd.read_sql_query("SELECT * FROM bloques", conn)
            id_b = st.selectbox("Bloque", blqs['id'].tolist(), format_func=lambda x: blqs[blqs['id']==x]['nombre'].values[0]) if not blqs.empty else None
            tip = st.text_input("Tipo Unidad")
            pre = st.number_input("Precio Alquiler", value=0.0)
            if st.form_submit_button("Guardar Unidad"):
                conn.execute("INSERT INTO inmuebles (id_bloque, tipo, precio_alquiler) VALUES (?,?,?)", (id_b, tip, pre))
                conn.commit(); st.success("Unidad Creada")

    with t4:
        st.write("### Generación Masiva")
        mes = st.text_input("Mes/Año (Ej: Mayo 2025)")
        if st.button("🚀 Generar Cuotas de Todos los Contratos"):
            conn = conectar()
            activos = pd.read_sql_query("SELECT id, monto_alquiler FROM contratos WHERE activo=1", conn)
            for _, c in activos.iterrows():
                conn.execute("INSERT INTO deudas (id_contrato, concepto, mes_anio, monto_debe) VALUES (?,?,?,?)",
                             (c['id'], "Alquiler", mes, c['monto_alquiler']))
            conn.commit(); st.success("Cuotas Generadas")

# ---------------------------------------------------------
# MÓDULO 3: NUEVO CONTRATO
# ---------------------------------------------------------
elif menu == "📝 Nuevo Contrato":
    st.subheader("Nuevo Alquiler")
    conn = conectar()
    inm_db = pd.read_sql_query("SELECT id, tipo FROM inmuebles", conn)
    inq_db = pd.read_sql_query("SELECT id, nombre FROM inquilinos", conn)
    
    with st.form("f_con"):
        c1, c2 = st.columns(2)
        id_inm = c1.selectbox("Unidad", inm_db['id'].tolist(), format_func=lambda x: f"{x}-{inm_db[inm_db['id']==x]['tipo'].values[0]}")
        id_inq = c2.selectbox("Inquilino", inq_db['id'].tolist(), format_func=lambda x: inq_db[inq_db['id']==x]['nombre'].values[0])
        f_ini = c1.date_input("Inicio", date.today())
        meses = c2.number_input("Meses", min_value=1, value=6)
        f_fin = f_ini + timedelta(days=meses * 30)
        monto = st.number_input("Alquiler Mensual", value=0.0)
        if st.form_submit_button("Grabar"):
            cur = conn.cursor()
            cur.execute("INSERT INTO contratos (id_inmueble, id_inquilino, fecha_inicio, fecha_fin, meses, activo, monto_alquiler) VALUES (?,?,?,?,?,1,?)",
                        (id_inm, id_inq, f_ini, f_fin, meses, monto))
            conn.commit(); st.success("Contrato grabado")

# ---------------------------------------------------------
# MÓDULO 4: COBRANZAS (WHATSAPP)
# ---------------------------------------------------------
elif menu == "💰 Cobranzas":
    st.subheader("Cobros")
    conn = conectar()
    query_c = """
        SELECT d.id, i.tipo, inq.nombre, d.monto_debe, d.monto_pago, inq.celular, d.concepto
        FROM deudas d JOIN contratos c ON d.id_contrato=c.id
        JOIN inmuebles i ON c.id_inmueble=i.id JOIN inquilinos inq ON c.id_inquilino=inq.id
        WHERE d.pagado = 0
    """
    df_c = pd.read_sql_query(query_c, conn)
    for _, row in df_c.iterrows():
        with st.expander(f"{row['tipo']} - {row['nombre']}"):
            saldo = row['monto_debe'] - row['monto_pago']
            st.write(f"Saldo: {fmt_moneda(saldo)}")
            pago = st.number_input("Monto", min_value=0.0, max_value=float(saldo), key=f"c_{row['id']}")
            if st.button("Confirmar Pago", key=f"b_{row['id']}"):
                nuevo = row['monto_pago'] + pago
                pagado = 1 if nuevo >= row['monto_debe'] else 0
                conn.execute("UPDATE deudas SET monto_pago=?, pagado=?, fecha_cobro=? WHERE id=?", (nuevo, pagado, date.today(), row['id']))
                conn.commit()
                msg = f"✅ RECIBO: {row['tipo']}\\nAbonado: {fmt_moneda(pago)}\\nSaldo: {fmt_moneda(saldo-pago)}"
                st.session_state[f'wa_{row["id"]}'] = crear_link_whatsapp(row['celular'], msg)
                st.rerun()
            if f'wa_{row["id"]}' in st.session_state:
                st.markdown(f'<a href="{st.session_state[f"wa_{row[id]}"]}" target="_blank"><button style="background-color:#25D366; color:white; border:none; padding:10px; border-radius:5px; width:100%">📲 WhatsApp</button></a>', unsafe_allow_html=True)

# ---------------------------------------------------------
# MÓDULO 5: MOROSOS Y CAJA
# ---------------------------------------------------------
elif menu == "🚨 Morosos":
    st.subheader("Deudores Pendientes")
    conn = conectar()
    df_m = pd.read_sql_query("""
        SELECT inq.nombre as Inquilino, i.tipo as Unidad, (d.monto_debe - d.monto_pago) as Saldo
        FROM deudas d JOIN contratos c ON d.id_contrato=c.id
        JOIN inmuebles i ON c.id_inmueble=i.id JOIN inquilinos inq ON c.id_inquilino=inq.id
        WHERE d.pagado = 0
    """, conn)
    if not df_m.empty:
        st.error(f"Total Mora: {fmt_moneda(df_m['Saldo'].sum())}")
        df_m['Saldo'] = df_m['Saldo'].apply(fmt_moneda)
        st.table(df_m)
    else: st.success("Sin deudas.")

elif menu == "📊 Caja":
    st.subheader("Ingresos Recaudados")
    df_caja = pd.read_sql_query("SELECT fecha_cobro as Fecha, concepto as Detalle, monto_pago as Monto FROM deudas WHERE pagado=1", conectar())
    if not df_caja.empty:
        st.metric("Total Recaudado", fmt_moneda(df_caja['Monto'].sum()))
        df_caja['Monto'] = df_caja['Monto'].apply(fmt_moneda)
        st.table(df_caja)
