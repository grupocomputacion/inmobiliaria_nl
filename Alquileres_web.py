import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, date, timedelta
import urllib.parse
import os
import io

# --- 1. CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Inmobiliaria Pro Cloud", layout="wide", initial_sidebar_state="expanded")

# --- 2. FUNCIONES DE MOTOR ---
def conectar():
    return sqlite3.connect('datos_alquileres.db', check_same_thread=False)

def fmt_moneda(valor):
    """Visualización profesional: $ 1.250.000"""
    try:
        return f"$ {int(float(valor or 0)):,}".replace(",", ".")
    except:
        return "$ 0"

def limpiar_monto(texto):
    """Limpia puntos y símbolos para guardar como número puro en la DB"""
    if isinstance(texto, (int, float)): return float(texto)
    try:
        # Quitamos puntos de miles y dejamos el número limpio
        return float(str(texto).replace('$', '').replace('.', '').replace(',', '').strip() or 0)
    except:
        return 0.0

def crear_link_whatsapp(tel, mensaje):
    tel_limpio = "".join(filter(str.isdigit, str(tel)))
    texto = urllib.parse.quote(mensaje)
    return f"https://wa.me/{tel_limpio}?text={texto}"

def inicializar_absoluto():
    """Borrado físico del archivo para asegurar limpieza total de la estructura"""
    if os.path.exists('datos_alquileres.db'):
        os.remove('datos_alquileres.db')
    
    conn = conectar()
    c = conn.cursor()
    c.executescript('''
        CREATE TABLE bloques (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT UNIQUE);
        CREATE TABLE inmuebles (
            id INTEGER PRIMARY KEY AUTOINCREMENT, id_bloque INTEGER, tipo TEXT, 
            precio_alquiler REAL, costo_contrato REAL, deposito_base REAL,
            UNIQUE(id_bloque, tipo)
        );
        CREATE TABLE inquilinos (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT, celular TEXT);
        CREATE TABLE contratos (
            id INTEGER PRIMARY KEY AUTOINCREMENT, id_inmueble INTEGER, id_inquilino INTEGER, 
            fecha_inicio DATE, fecha_fin DATE, meses INTEGER, activo INTEGER DEFAULT 1, 
            monto_alquiler REAL, monto_contrato REAL, monto_deposito REAL
        );
        CREATE TABLE deudas (
            id INTEGER PRIMARY KEY AUTOINCREMENT, id_contrato INTEGER, concepto TEXT, 
            mes_anio TEXT, monto_debe REAL, monto_pago REAL DEFAULT 0, pagado INTEGER DEFAULT 0, fecha_cobro DATE
        );
    ''')
    conn.commit()
    conn.close()

# Asegurar que la DB exista al arrancar
if not os.path.exists('datos_alquileres.db'):
    inicializar_absoluto()

# --- 3. MENÚ LATERAL ---
with st.sidebar:
    st.title("🏢 Inmobiliaria Pro")
    if st.button("🚨 REINICIAR TODA LA BASE"):
        inicializar_absoluto()
        st.cache_data.clear()
        st.success("Base de datos reseteada al 100%.")
        st.rerun()
    
    st.divider()
    menu = st.radio(
        "Navegación:",
        ["🏠 1. Inventario", "📝 2. Nuevo Contrato", "💰 3. Cobranzas", "🚨 4. Morosos", "📊 5. Caja", "⚙️ 6. Maestros"],
        label_visibility="collapsed"
    )

# ---------------------------------------------------------
# 1. INVENTARIO
# ---------------------------------------------------------
if menu == "🏠 1. Inventario":
    st.subheader("Estado de Unidades y Disponibilidad")
    conn = conectar()
    hoy = date.today()
    
    query = """
        SELECT i.id, b.nombre as Bloque, i.tipo as Unidad, 
               i.precio_alquiler, i.costo_contrato, i.deposito_base,
               c.fecha_inicio, c.fecha_fin, c.activo
        FROM inmuebles i
        JOIN bloques b ON i.id_bloque = b.id
        LEFT JOIN contratos c ON i.id = c.id_inmueble AND c.activo = 1
        GROUP BY i.id 
    """
    df = pd.read_sql_query(query, conn)

    if not df.empty:
        def calc_sit(row):
            if pd.isna(row['fecha_inicio']) or row['activo'] == 0: return "Libre", "LIBRE HOY"
            try:
                f_fin = pd.to_datetime(row['fecha_fin']).date()
                if hoy <= f_fin: return "OCUPADO", f_fin.strftime('%d/%m/%Y')
                else: return "VENCIDO", "LIBRE HOY"
            except: return "Libre", "LIBRE HOY"

        df[['Situación', 'Disponible Desde']] = df.apply(lambda x: pd.Series(calc_sit(x)), axis=1)
        df['Alquiler'] = df['precio_alquiler'].apply(fmt_moneda)
        df['Contrato'] = df['costo_contrato'].apply(fmt_moneda)
        df['Depósito'] = df['deposito_base'].apply(fmt_moneda)
        
        def color_sit(val):
            if val == "Libre": color = '#28a745'
            elif val == "OCUPADO": color = '#dc3545'
            else: color = '#fd7e14'
            return f'color: {color}; font-weight: bold'

        st.dataframe(df[["Bloque", "Unidad", "Situación", "Disponible Desde", "Alquiler", "Contrato", "Depósito"]].style.applymap(color_sit, subset=['Situación']), 
                     use_container_width=True, hide_index=True)
    else:
        st.info("No hay unidades cargadas. Vaya a la sección 6. Maestros.")

# ---------------------------------------------------------
# 2. NUEVO CONTRATO
# ---------------------------------------------------------
elif menu == "📝 2. Nuevo Contrato":
    st.subheader("Alta de Nuevo Contrato")
    conn = conectar()
    inm_db = pd.read_sql_query("SELECT id, tipo, precio_alquiler, costo_contrato, deposito_base FROM inmuebles", conn)
    inq_db = pd.read_sql_query("SELECT id, nombre FROM inquilinos", conn)
    
    if not inm_db.empty and not inq_db.empty:
        with st.form("f_con"):
            c1, c2 = st.columns(2)
            id_inm = c1.selectbox("Unidad", inm_db['id'].tolist(), format_func=lambda x: f"{inm_db[inm_db['id']==x]['tipo'].values[0]}")
            id_inq = c2.selectbox("Inquilino", inq_db['id'].tolist(), format_func=lambda x: inq_db[inq_db['id']==x]['nombre'].values[0])
            f_ini = c1.date_input("Fecha Inicio", date.today())
            meses = c2.number_input("Duración (Meses)", min_value=1, value=6)
            f_fin = f_ini + timedelta(days=meses * 30)
            
            val_ref = inm_db[inm_db['id'] == id_inm].iloc[0]
            st.info(f"Sugerido por Maestro: Alq: {fmt_moneda(val_ref['precio_alquiler'])} | Vence: {f_fin.strftime('%d/%m/%Y')}")
            
            # Inputs tipo texto para permitir puntos de miles
            m_alq_txt = c1.text_input("Monto Alquiler Mensual", value=str(int(val_ref['precio_alquiler'])))
            m_con_txt = c2.text_input("Costo Contrato Total", value=str(int(val_ref['costo_contrato'])))
            m_dep_txt = c1.text_input("Depósito de Garantía", value=str(int(val_ref['deposito_base'])))

            if st.form_submit_button("Grabar Contrato"):
                m_alq = limpiar_monto(m_alq_txt)
                m_con = limpiar_monto(m_con_txt)
                m_dep = limpiar_monto(m_dep_txt)
                cur = conn.cursor()
                cur.execute("""INSERT INTO contratos (id_inmueble, id_inquilino, fecha_inicio, fecha_fin, meses, activo, monto_alquiler, monto_contrato, monto_deposito) 
                               VALUES (?,?,?,?,?,1,?,?,?)""", (id_inm, id_inq, f_ini, f_fin, meses, m_alq, m_con, m_dep))
                conn.commit(); st.success("Contrato grabado con éxito"); st.rerun()
    else: st.warning("Cargue unidades e inquilinos en Maestros primero.")

# ---------------------------------------------------------
# 3. COBRANZAS (CON RECIBO WHATSAPP)
# ---------------------------------------------------------
elif menu == "💰 3. Cobranzas":
    st.subheader("Gestión de Cobros")
    conn = conectar()
    df_c = pd.read_sql_query("""
        SELECT d.id, i.tipo, inq.nombre, d.monto_debe, d.monto_pago, inq.celular, d.concepto
        FROM deudas d JOIN contratos c ON d.id_contrato=c.id
        JOIN inmuebles i ON c.id_inmueble=i.id JOIN inquilinos inq ON c.id_inquilino=inq.id
        WHERE d.pagado = 0
    """, conn)
    
    if not df_c.empty:
        for _, row in df_c.iterrows():
            with st.expander(f"📍 {row['tipo']} - {row['nombre']} ({row['concepto']})"):
                saldo = row['monto_debe'] - row['monto_pago']
                st.write(f"Saldo Pendiente: **{fmt_moneda(saldo)}**")
                pago_txt = st.text_input("Monto a cobrar", value=str(int(saldo)), key=f"c_{row['id']}")
                
                if st.button("Confirmar Pago", key=f"b_{row['id']}"):
                    pago = limpiar_monto(pago_txt)
                    nuevo = row['monto_pago'] + pago
                    pagado = 1 if nuevo >= row['monto_debe'] else 0
                    conn.execute("UPDATE deudas SET monto_pago=?, pagado=?, fecha_cobro=? WHERE id=?", (nuevo, pagado, date.today(), row['id']))
                    conn.commit()
                    msg = f"✅ *RECIBO*\\nUnidad: {row['tipo']}\\nAbonado: {fmt_moneda(pago)}\\nSaldo restante: {fmt_moneda(saldo-pago)}"
                    st.session_state[f'wa_{row["id"]}'] = crear_link_whatsapp(row['celular'], msg)
                    st.rerun()
                
                if f'wa_{row["id"]}' in st.session_state:
                    st.markdown(f'<a href="{st.session_state[f"wa_{row[id]}"]}" target="_blank"><button style="background-color:#25D366; color:white; border:none; padding:12px; border-radius:8px; width:100%; cursor:pointer; font-weight:bold;">📲 Enviar por WhatsApp</button></a>', unsafe_allow_html=True)
    else: st.info("No hay deudas pendientes de cobro.")

# ---------------------------------------------------------
# 4. MOROSOS
# ---------------------------------------------------------
elif menu == "🚨 4. Morosos":
    st.subheader("Listado de Deudores")
    conn = conectar()
    df_m = pd.read_sql_query("""
        SELECT inq.nombre as Inquilino, i.tipo as Unidad, (d.monto_debe - d.monto_pago) as Saldo 
        FROM deudas d JOIN contratos c ON d.id_contrato=c.id 
        JOIN inmuebles i ON c.id_inmueble=i.id 
        JOIN inquilinos inq ON c.id_inquilino=inq.id 
        WHERE d.pagado = 0 ORDER BY Saldo DESC
    """, conn)
    if not df_m.empty:
        st.error(f"Total en Mora: {fmt_moneda(df_m['Saldo'].sum())}")
        df_m['Saldo'] = df_m['Saldo'].apply(fmt_moneda)
        st.table(df_m)
    else: st.success("🎉 Todas las cuentas están al día.")

# ---------------------------------------------------------
# 5. CAJA
# ---------------------------------------------------------
elif menu == "📊 5. Caja":
    st.subheader("Ingresos Reales Recaudados")
    df_cj = pd.read_sql_query("SELECT fecha_cobro as Fecha, concepto as Detalle, monto_pago as Monto FROM deudas WHERE pagado=1", conectar())
    if not df_cj.empty:
        st.metric("Total Recaudado", fmt_moneda(df_cj['Monto'].sum()))
        df_cj['Monto'] = df_cj['Monto'].apply(fmt_moneda)
        st.table(df_cj)
    else: st.info("No hay ingresos registrados en la caja.")

# ---------------------------------------------------------
# 6. MAESTROS
# ---------------------------------------------------------
elif menu == "⚙️ 6. Maestros":
    st.subheader("Administración de Datos Maestros")
    t1, t2, t3, t4 = st.tabs(["👤 Inquilinos", "🏢 Bloques", "🏠 Unidades", "⚡ Procesos"])
    
    with t3:
        con = conectar()
        bls = pd.read_sql_query("SELECT * FROM bloques", con)
        col_a, col_b = st.columns(2)
        
        with col_a:
            st.write("### ➕ Nueva Unidad")
            if not bls.empty:
                with st.form("f_maestro_alta"):
                    idb = st.selectbox("Bloque", bls['id'].tolist(), format_func=lambda x: bls[bls['id']==x]['nombre'].values[0])
                    tp = st.text_input("Nombre/Nro Unidad")
                    pr_txt = st.text_input("Precio Alquiler ($)", value="0")
                    co_txt = st.text_input("Costo Contrato ($)", value="0")
                    de_txt = st.text_input("Depósito ($)", value="0")
                    st.caption("Escriba montos sin puntos o con puntos (ej: 390.000)")
                    if st.form_submit_button("💾 Guardar"):
                        pr = limpiar_monto(pr_txt); co = limpiar_monto(co_txt); de = limpiar_monto(de_txt)
                        try:
                            con.execute("INSERT INTO inmuebles (id_bloque, tipo, precio_alquiler, costo_contrato, deposito_base) VALUES (?,?,?,?,?)", (idb, tp, pr, co, de))
                            con.commit(); st.success("Unidad creada"); st.rerun()
                        except: st.error("Error: Esa unidad ya existe.")
            else: st.warning("Cargue un bloque primero.")

        with col_b:
            st.write("### ✏️ Editar Precios")
            inm_ex = pd.read_sql_query("SELECT i.id, b.nombre || ' - ' || i.tipo as disp FROM inmuebles i JOIN bloques b ON i.id_bloque = b.id", con)
            if not inm_ex.empty:
                id_ed = st.selectbox("Seleccionar Unidad", inm_ex['id'].tolist(), format_func=lambda x: inm_ex[inm_ex['id']==x]['disp'].values[0])
                curr = pd.read_sql_query(f"SELECT * FROM inmuebles WHERE id={id_ed}", con).iloc[0]
                with st.form("f_edit"):
                    n_pr = st.text_input("Nuevo Alquiler", value=str(int(curr['precio_alquiler'])))
                    n_co = st.text_input("Nuevo Contrato", value=str(int(curr['costo_contrato'])))
                    n_de = st.text_input("Nuevo Depósito", value=str(int(curr['deposito_base'])))
                    if st.form_submit_button("🔄 Actualizar"):
                        con.execute("UPDATE inmuebles SET precio_alquiler=?, costo_contrato=?, deposito_base=? WHERE id=?", (limpiar_monto(n_pr), limpiar_monto(n_co), limpiar_monto(n_de), id_ed))
                        con.commit(); st.success("Precios actualizados"); st.rerun()

    with t1:
        with st.form("f_inq"):
            nom = st.text_input("Nombre Inquilino"); tel = st.text_input("WhatsApp (549...)")
            if st.form_submit_button("Guardar"):
                con = conectar(); con.execute("INSERT INTO inquilinos (nombre, celular) VALUES (?,?)", (nom, tel)); con.commit(); st.success("Inquilino creado"); st.rerun()
    with t2:
        with st.form("f_bl"):
            nb = st.text_input("Nombre del Bloque")
            if st.form_submit_button("Guardar"):
                con = conectar(); con.execute("INSERT INTO bloques (nombre) VALUES (?)", (nb,)); con.commit(); st.success("Bloque creado"); st.rerun()
    with t4:
        st.write("### Procesos Masivos")
        mes = st.text_input("Mes/Año (Ej: Junio 2025)")
        if st.button("🚀 Generar Cuotas Mensuales"):
            con = conectar(); activos = pd.read_sql_query("SELECT id, monto_alquiler FROM contratos WHERE activo=1", con)
            for _, c in activos.iterrows():
                con.execute("INSERT INTO deudas (id_contrato, concepto, mes_anio, monto_debe) VALUES (?,?,?,?)", (c['id'], "Alquiler", mes, c['monto_alquiler']))
            con.commit(); st.success("Cuotas generadas exitosamente")
