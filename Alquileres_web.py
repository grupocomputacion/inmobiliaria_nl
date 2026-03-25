import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, date, timedelta
import os

# ==========================================
# 1. CONFIGURACIÓN Y LIMPIEZA TOTAL
# ==========================================
st.set_page_config(page_title="NL PROPIEDADES - PANEL TOTAL", layout="wide")

# Forzamos conexión limpia
if os.path.exists('datos_alquileres.db'):
    conn = sqlite3.connect('datos_alquileres.db', check_same_thread=False)
else:
    conn = sqlite3.connect('datos_alquileres.db', check_same_thread=False)

cur = conn.cursor()
cur.executescript('''
    CREATE TABLE IF NOT EXISTS bloques (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT UNIQUE);
    CREATE TABLE IF NOT EXISTS inmuebles (id INTEGER PRIMARY KEY AUTOINCREMENT, id_bloque INTEGER, tipo TEXT, precio_alquiler INTEGER, costo_contrato INTEGER, deposito_base INTEGER);
    CREATE TABLE IF NOT EXISTS inquilinos (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT, dni TEXT);
    CREATE TABLE IF NOT EXISTS contratos (id INTEGER PRIMARY KEY AUTOINCREMENT, id_inmueble INTEGER, id_inquilino INTEGER, fecha_inicio DATE, fecha_fin DATE, activo INTEGER DEFAULT 1, monto_alquiler INTEGER);
    CREATE TABLE IF NOT EXISTS deudas (id INTEGER PRIMARY KEY AUTOINCREMENT, id_contrato INTEGER, concepto TEXT, monto_debe INTEGER, monto_pago INTEGER DEFAULT 0, pagado INTEGER DEFAULT 0);
''')
conn.commit()

def cl(t): return int(str(t).replace('$', '').replace('.', '').replace(',', '').strip() or 0)

# ==========================================
# 2. VISTA ÚNICA (SCROLL INFINITO)
# ==========================================
st.title("🏠 NL PROPIEDADES - GESTIÓN INTEGRAL")
st.warning("⚠️ MODO PRESENTACIÓN: Todas las funciones están desplegadas debajo.")

# --- SECCIÓN MAESTROS (CARGA INICIAL) ---
st.header("⚙️ 1. Configuración de Datos (Maestros)")
col_m1, col_m2, col_m3 = st.columns(3)

with col_m1:
    st.subheader("Inquilinos")
    with st.form("f_inq", clear_on_submit=True):
        n = st.text_input("Nombre"); d = st.text_input("DNI")
        if st.form_submit_button("Guardar Inquilino"):
            cur.execute("INSERT INTO inquilinos (nombre, dni) VALUES (?,?)", (n, d))
            conn.commit(); st.rerun()
    st.dataframe(pd.read_sql_query("SELECT * FROM inquilinos", conn), height=150)

with col_m2:
    st.subheader("Bloques")
    nb = st.text_input("Nombre Bloque")
    if st.button("Guardar Bloque"):
        cur.execute("INSERT INTO bloques (nombre) VALUES (?)", (nb,))
        conn.commit(); st.rerun()
    st.dataframe(pd.read_sql_query("SELECT * FROM bloques", conn), height=150)

with col_m3:
    st.subheader("Unidades")
    bls = pd.read_sql_query("SELECT * FROM bloques", conn)
    if not bls.empty:
        with st.form("f_uni", clear_on_submit=True):
            bid = st.selectbox("Bloque", bls['id'].tolist(), format_func=lambda x: bls[bls['id']==x]['nombre'].values[0])
            ut = st.text_input("Unidad")
            p1 = st.text_input("Alquiler Sugerido")
            if st.form_submit_button("Guardar Unidad"):
                cur.execute("INSERT INTO inmuebles (id_bloque, tipo, precio_alquiler) VALUES (?,?,?)", (bid, ut, cl(p1)))
                conn.commit(); st.rerun()
    st.dataframe(pd.read_sql_query("SELECT * FROM inmuebles", conn), height=150)

st.divider()

# --- SECCIÓN CONTRATOS ---
st.header("📝 2. Nuevo Contrato")
u_df = pd.read_sql_query("SELECT i.id, b.nombre || ' - ' || i.tipo as ref, i.precio_alquiler FROM inmuebles i JOIN bloques b ON i.id_bloque=b.id", conn)
i_df = pd.read_sql_query("SELECT id, nombre FROM inquilinos", conn)

if not u_df.empty and not i_df.empty:
    with st.form("f_con"):
        c1, c2, c3 = st.columns(3)
        sel_u = c1.selectbox("Unidad", u_df['id'].tolist(), format_func=lambda x: u_df[u_df['id']==x]['ref'].values[0])
        sel_i = c2.selectbox("Inquilino", i_df['id'].tolist(), format_func=lambda x: i_df[i_df['id']==x]['nombre'].values[0])
        f_ini = c3.date_input("Inicio", date.today())
        m_alq = st.text_input("Monto Alquiler Final", value=str(u_df[u_df['id']==sel_u]['precio_alquiler'].values[0]))
        if st.form_submit_button("GENERAR CONTRATO"):
            cur.execute("INSERT INTO contratos (id_inmueble, id_inquilino, fecha_inicio, monto_alquiler) VALUES (?,?,?,?)", (sel_u, sel_i, f_ini, cl(m_alq)))
            cid = cur.lastrowid
            cur.execute("INSERT INTO deudas (id_contrato, concepto, monto_debe) VALUES (?, 'Mes 1', ?)", (cid, cl(m_alq)))
            conn.commit(); st.success("Contrato Creado!"); st.rerun()

st.divider()

# --- SECCIÓN COBRANZAS ---
st.header("💰 3. Cobranzas")
deu = pd.read_sql_query("SELECT d.id, inq.nombre, i.tipo, d.concepto, d.monto_debe, d.monto_pago FROM deudas d JOIN contratos c ON d.id_contrato=c.id JOIN inmuebles i ON c.id_inmueble=i.id JOIN inquilinos inq ON c.id_inquilino=inq.id WHERE d.pagado=0", conn)
if not deu.empty:
    cols_c = st.columns(2)
    for idx, r in deu.iterrows():
        with cols_c[idx % 2].expander(f"{r['nombre']} - {r['tipo']} (Debe: ${r['monto_debe']-r['monto_pago']})"):
            m_p = st.text_input("Monto a pagar", value=str(r['monto_debe']-r['monto_pago']), key=f"p_{r['id']}")
            if st.button("Confirmar Pago", key=f"b_{r['id']}"):
                cur.execute("UPDATE deudas SET monto_pago=?, pagado=1 WHERE id=?", (cl(m_p), r['id']))
                conn.commit(); st.rerun()
else:
    st.info("No hay deudas.")

st.divider()

# --- SECCIÓN CAJA Y MOROSOS ---
caja_col, moroso_col = st.columns(2)

with caja_col:
    st.header("📊 4. Caja")
    st.dataframe(pd.read_sql_query("SELECT concepto, monto_pago as Importe FROM deudas WHERE pagado=1", conn), use_container_width=True)

with moroso_col:
    st.header("🚨 5. Morosos")
    st.dataframe(pd.read_sql_query("SELECT inq.nombre, d.monto_debe as Saldo FROM deudas d JOIN contratos c ON d.id_contrato=c.id JOIN inquilinos inq ON c.id_inquilino=inq.id WHERE d.pagado=0", conn), use_container_width=True)

# --- INVENTARIO AL FINAL ---
st.divider()
st.header("🏠 6. Inventario de Unidades")
st.dataframe(pd.read_sql_query("SELECT b.nombre as Bloque, i.tipo as Unidad, i.precio_alquiler FROM inmuebles i JOIN bloques b ON i.id_bloque=b.id", conn), use_container_width=True)
