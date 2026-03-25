import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, date, timedelta
import os

# 1. CONFIGURACIÓN E IDENTIDAD
st.set_page_config(page_title="NL PROPIEDADES", layout="wide")

st.markdown("""
    <style>
    .stButton>button { background-color: #D4AF37; color: black; font-weight: bold; width: 100%; border-radius: 5px; }
    h1, h2, h3 { color: #D4AF37; }
    </style>
    """, unsafe_allow_html=True)

# 2. BASE DE DATOS (CONEXIÓN Y CREACIÓN)
def get_connection():
    return sqlite3.connect('datos_alquileres.db', check_same_thread=False)

conn = get_connection()
cur = conn.cursor()

# Estructura Limpia
cur.executescript('''
    CREATE TABLE IF NOT EXISTS bloques (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT UNIQUE);
    CREATE TABLE IF NOT EXISTS inmuebles (id INTEGER PRIMARY KEY AUTOINCREMENT, id_bloque INTEGER, tipo TEXT, precio_alquiler INTEGER, costo_contrato INTEGER, deposito_base INTEGER);
    CREATE TABLE IF NOT EXISTS inquilinos (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT, dni TEXT, celular TEXT);
    CREATE TABLE IF NOT EXISTS contratos (id INTEGER PRIMARY KEY AUTOINCREMENT, id_inmueble INTEGER, id_inquilino INTEGER, fecha_inicio DATE, fecha_fin DATE, meses INTEGER, activo INTEGER DEFAULT 1, monto_alquiler INTEGER, monto_contrato INTEGER, monto_deposito INTEGER);
    CREATE TABLE IF NOT EXISTS deudas (id INTEGER PRIMARY KEY AUTOINCREMENT, id_contrato INTEGER, concepto TEXT, mes_anio TEXT, monto_debe INTEGER, monto_pago INTEGER DEFAULT 0, pagado INTEGER DEFAULT 0, fecha_cobro DATE);
''')
conn.commit()

# Utilidades
def cl(t): return int(str(t).replace('$', '').replace('.', '').replace(',', '').strip() or 0)
def f_m(v): return f"$ {int(v or 0):,}".replace(",", ".")

# 3. NAVEGACIÓN (LÓGICA BLINDADA)
with st.sidebar:
    st.title("NL PROPIEDADES")
    st.write("---")
    menu = st.radio("MENÚ:", ["1. Inventario", "2. Nuevo Contrato", "3. Cobranzas", "4. Morosos", "5. Caja", "6. Maestros"])
    st.write("---")
    if st.button("🚨 RESETEAR SISTEMA"):
        if os.path.exists('datos_alquileres.db'):
            conn.close()
            os.remove('datos_alquileres.db')
            st.rerun()

# --- SECCIONES ---

if menu == "1. Inventario":
    st.header("🏠 1. Inventario")
    try:
        df = pd.read_sql_query("""SELECT b.nombre as Bloque, i.tipo as Unidad, i.precio_alquiler as Alquiler, MAX(c.activo) as ocupado FROM inmuebles i JOIN bloques b ON i.id_bloque = b.id LEFT JOIN contratos c ON i.id = c.id_inmueble AND c.activo = 1 GROUP BY i.id""", conn)
        if not df.empty:
            df['Estado'] = df['ocupado'].apply(lambda x: "🔴 OCUPADO" if x == 1 else "🟢 LIBRE")
            st.dataframe(df[["Bloque", "Unidad", "Estado", "Alquiler"]], use_container_width=True)
        else: st.info("Sin datos.")
    except Exception as e: st.error(f"Error: {e}")

if menu == "2. Nuevo Contrato":
    st.header("📝 2. Nuevo Contrato")
    try:
        u_df = pd.read_sql_query("SELECT i.id, b.nombre || ' - ' || i.tipo as ref, i.precio_alquiler, i.costo_contrato, i.deposito_base FROM inmuebles i JOIN bloques b ON i.id_bloque=b.id", conn)
        i_df = pd.read_sql_query("SELECT id, nombre FROM inquilinos", conn)
        if not u_df.empty and not i_df.empty:
            with st.form("f_alta"):
                sel_u = st.selectbox("Unidad", u_df['id'].tolist(), format_func=lambda x: u_df[u_df['id']==x]['ref'].values[0])
                sel_i = st.selectbox("Inquilino", i_df['id'].tolist(), format_func=lambda x: i_df[i_df['id']==x]['nombre'].values[0])
                f_ini = st.date_input("Inicio", date.today())
                meses = st.number_input("Meses", 1, 60, 6)
                row = u_df[u_df['id']==sel_u].iloc[0]
                m1 = st.text_input("Alquiler", value=str(row['precio_alquiler']))
                m2 = st.text_input("Contrato", value=str(row['costo_contrato']))
                m3 = st.text_input("Deposito", value=str(row['deposito_base']))
                if st.form_submit_button("GRABAR"):
                    cur.execute("INSERT INTO contratos (id_inmueble, id_inquilino, fecha_inicio, fecha_fin, meses, monto_alquiler, monto_contrato, monto_deposito) VALUES (?,?,?,?,?,?,?,?)", (sel_u, sel_i, f_ini, f_ini + timedelta(days=meses*30), meses, cl(m1), cl(m2), cl(m3)))
                    cid = cur.lastrowid
                    m_txt = f_ini.strftime("%m/%y")
                    cur.executemany("INSERT INTO deudas (id_contrato, concepto, mes_anio, monto_debe) VALUES (?,?,?,?)", [(cid, "Contrato", m_txt, cl(m2)), (cid, "Deposito", m_txt, cl(m3)), (cid, "Alquiler 1", m_txt, cl(m1))])
                    conn.commit(); st.success("GRABADO"); st.rerun()
        else: st.warning("Cargue Inquilinos y Unidades en Maestros.")
    except Exception as e: st.error(f"Error: {e}")

if menu == "3. Cobranzas":
    st.header("💰 3. Cobranzas")
    try:
        deu = pd.read_sql_query("SELECT d.id, inq.nombre, i.tipo, d.concepto, d.monto_debe, d.monto_pago FROM deudas d JOIN contratos c ON d.id_contrato=c.id JOIN inmuebles i ON c.id_inmueble=i.id JOIN inquilinos inq ON c.id_inquilino=inq.id WHERE d.pagado=0", conn)
        for _, r in deu.iterrows():
            with st.expander(f"{r['nombre']} - {r['tipo']} ({r['concepto']})"):
                m_c = st.text_input("Monto", value=str(r['monto_debe']-r['monto_pago']), key=f"c_{r['id']}")
                if st.button("Cobrar", key=f"b_{r['id']}"):
                    cur.execute("UPDATE deudas SET monto_pago=?, pagado=1, fecha_cobro=? WHERE id=?", (cl(m_c), date.today(), r['id']))
                    conn.commit(); st.rerun()
    except Exception as e: st.error(f"Error: {e}")

if menu == "4. Morosos":
    st.header("🚨 4. Morosos")
    try:
        df_m = pd.read_sql_query("SELECT inq.nombre as Inquilino, i.tipo as Unidad, d.concepto, (d.monto_debe-d.monto_pago) as Saldo FROM deudas d JOIN contratos c ON d.id_contrato=c.id JOIN inmuebles i ON c.id_inmueble=i.id JOIN inquilinos inq ON c.id_inquilino=inq.id WHERE d.pagado=0", conn)
        st.table(df_m)
    except Exception as e: st.error(f"Error: {e}")

if menu == "5. Caja":
    st.header("📊 5. Caja")
    try:
        df_c = pd.read_sql_query("SELECT fecha_cobro, concepto, monto_pago FROM deudas WHERE pagado=1", conn)
        st.dataframe(df_c, use_container_width=True)
    except Exception as e: st.error(f"Error: {e}")

if menu == "6. Maestros":
    st.header("⚙️ 6. Maestros")
    tab1, tab2, tab3 = st.tabs(["Inquilinos", "Bloques", "Unidades"])
    with tab1:
        with st.form("f1"):
            n = st.text_input("Nombre"); d = st.text_input("DNI")
            if st.form_submit_button("Cargar"):
                cur.execute("INSERT INTO inquilinos (nombre, dni) VALUES (?,?)", (n, d))
                conn.commit(); st.rerun()
        st.dataframe(pd.read_sql_query("SELECT * FROM inquilinos", conn), use_container_width=True)
    with tab2:
        nb = st.text_input("Nuevo Bloque")
        if st.button("Guardar Bloque"):
            cur.execute("INSERT INTO bloques (nombre) VALUES (?)", (nb,))
            conn.commit(); st.rerun()
        st.table(pd.read_sql_query("SELECT * FROM bloques", conn))
    with tab3:
        bls = pd.read_sql_query("SELECT * FROM bloques", conn)
        if not bls.empty:
            with st.form("f3"):
                bid = st.selectbox("Bloque", bls['id'].tolist(), format_func=lambda x: bls[bls['id']==x]['nombre'].values[0])
                ut = st.text_input("Unidad")
                p1 = st.text_input("Alquiler Sugerido"); p2 = st.text_input("Contrato Sugerido"); p3 = st.text_input("Deposito Sugerido")
                if st.form_submit_button("Guardar Unidad"):
                    cur.execute("INSERT INTO inmuebles (id_bloque, tipo, precio_alquiler, costo_contrato, deposito_base) VALUES (?,?,?,?,?)", (bid, ut, cl(p1), cl(p2), cl(p3)))
                    conn.commit(); st.rerun()
        st.dataframe(pd.read_sql_query("SELECT i.id, b.nombre as Bloque, i.tipo as Unidad FROM inmuebles i JOIN bloques b ON i.id_bloque=b.id", conn), use_container_width=True)
