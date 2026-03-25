import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, date, timedelta
import os

# 1. CONFIGURACIÓN DE PÁGINA
st.set_page_config(page_title="NL Propiedades - DEBUG MODE", layout="wide", initial_sidebar_state="expanded")

# 2. ESTILOS NL
st.markdown("""
    <style>
    .stButton>button { background-color: #D4AF37; color: black; font-weight: bold; width: 100%; border-radius: 5px; }
    h1, h2, h3 { color: #D4AF37; }
    .error-box { padding: 10px; background-color: #ff4b4b; color: white; border-radius: 5px; margin: 10px 0; }
    </style>
    """, unsafe_allow_html=True)

# 3. BASE DE DATOS Y MIGRACIÓN FORZADA
def conectar():
    return sqlite3.connect('datos_alquileres.db', check_same_thread=False)

conn = conectar()
cur = conn.cursor()

# Aseguramos estructura
cur.executescript('''
    CREATE TABLE IF NOT EXISTS bloques (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT UNIQUE);
    CREATE TABLE IF NOT EXISTS inmuebles (id INTEGER PRIMARY KEY AUTOINCREMENT, id_bloque INTEGER, tipo TEXT, precio_alquiler INTEGER, costo_contrato INTEGER, deposito_base INTEGER);
    CREATE TABLE IF NOT EXISTS inquilinos (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT, celular TEXT, dni TEXT, procedencia TEXT);
    CREATE TABLE IF NOT EXISTS contratos (id INTEGER PRIMARY KEY AUTOINCREMENT, id_inmueble INTEGER, id_inquilino INTEGER, fecha_inicio DATE, fecha_fin DATE, meses INTEGER, activo INTEGER DEFAULT 1, monto_alquiler INTEGER, monto_contrato INTEGER, monto_deposito INTEGER);
    CREATE TABLE IF NOT EXISTS deudas (id INTEGER PRIMARY KEY AUTOINCREMENT, id_contrato INTEGER, concepto TEXT, mes_anio TEXT, monto_debe INTEGER, monto_pago INTEGER DEFAULT 0, pagado INTEGER DEFAULT 0, fecha_cobro DATE);
''')
conn.commit()

# --- FUNCIONES DE LIMPIEZA ---
def cl(t): return int(str(t).replace('$', '').replace('.', '').replace(',', '').strip() or 0)
def f_m(v): return f"$ {int(v or 0):,}".replace(",", ".")

# 4. BARRA LATERAL
with st.sidebar:
    st.title("NL PROPIEDADES")
    st.write("---")
    # Menu con números claros
    menu = st.radio("NAVEGACIÓN:", ["1. Inventario", "2. Nuevo Contrato", "3. Cobranzas", "4. Morosos", "5. Caja", "6. Maestros"])
    st.write("---")
    if st.button("🚨 BORRAR BASE Y EMPEZAR DE CERO"):
        if os.path.exists('datos_alquileres.db'):
            conn.close()
            os.remove('datos_alquileres.db')
            st.rerun()

# ==========================================
# SECCIÓN 1: INVENTARIO
# ==========================================
if "1. Inventario" in menu:
    st.header("🏠 1. Inventario")
    try:
        df = pd.read_sql_query("""SELECT b.nombre as Bloque, i.tipo as Unidad, i.precio_alquiler, MAX(c.activo) as ocupado FROM inmuebles i JOIN bloques b ON i.id_bloque = b.id LEFT JOIN contratos c ON i.id = c.id_inmueble AND c.activo = 1 GROUP BY i.id""", conn)
        if not df.empty:
            df['Estado'] = df['ocupado'].apply(lambda x: "🔴 OCUPADO" if x == 1 else "🟢 LIBRE")
            st.dataframe(df, use_container_width=True)
        else: st.info("No hay unidades. Cargue datos en la Sección 6.")
    except Exception as e:
        st.error(f"Error en Sección 1: {e}")

# ==========================================
# SECCIÓN 2: NUEVO CONTRATO
# ==========================================
if "2. Nuevo Contrato" in menu:
    st.header("📝 2. Nuevo Contrato")
    try:
        inm = pd.read_sql_query("SELECT i.id, b.nombre || ' - ' || i.tipo as ref, i.precio_alquiler, i.costo_contrato, i.deposito_base FROM inmuebles i JOIN bloques b ON i.id_bloque=b.id", conn)
        inq = pd.read_sql_query("SELECT id, nombre FROM inquilinos", conn)
        if not inm.empty and not inq.empty:
            with st.form("form_2"):
                u_id = st.selectbox("Unidad", inm['id'].tolist(), format_func=lambda x: inm[inm['id']==x]['ref'].values[0])
                i_id = st.selectbox("Inquilino", inq['id'].tolist(), format_func=lambda x: inq[inq['id']==x]['nombre'].values[0])
                f_ini = st.date_input("Inicio", date.today())
                meses = st.number_input("Meses", 1, 60, 6)
                row = inm[inm['id']==u_id].iloc[0]
                m1 = st.text_input("Alquiler", value=str(row['precio_alquiler']))
                m2 = st.text_input("Contrato", value=str(row['costo_contrato']))
                m3 = st.text_input("Depósito", value=str(row['deposito_base']))
                if st.form_submit_button("GRABAR CONTRATO"):
                    cur.execute("INSERT INTO contratos (id_inmueble, id_inquilino, fecha_inicio, fecha_fin, meses, monto_alquiler, monto_contrato, monto_deposito) VALUES (?,?,?,?,?,?,?,?)", (u_id, i_id, f_ini, f_ini + timedelta(days=meses*30), meses, cl(m1), cl(m2), cl(m3)))
                    cid = cur.lastrowid
                    m_txt = f_ini.strftime("%m/%y")
                    cur.executemany("INSERT INTO deudas (id_contrato, concepto, mes_anio, monto_debe) VALUES (?,?,?,?)", [(cid, "Contrato", m_txt, cl(m2)), (cid, "Depósito", m_txt, cl(m3)), (cid, "Mes 1", m_txt, cl(m1))])
                    conn.commit(); st.success("Guardado!"); st.rerun()
        else: st.warning("Cargue Inquilinos y Unidades primero.")
    except Exception as e:
        st.error(f"Error en Sección 2: {e}")

# ==========================================
# SECCIÓN 3: COBRANZAS
# ==========================================
if "3. Cobranzas" in menu:
    st.header("💰 3. Cobranzas")
    try:
        deudas = pd.read_sql_query("SELECT d.id, inq.nombre, i.tipo, d.concepto, d.monto_debe, d.monto_pago FROM deudas d JOIN contratos c ON d.id_contrato=c.id JOIN inmuebles i ON c.id_inmueble=i.id JOIN inquilinos inq ON c.id_inquilino=inq.id WHERE d.pagado=0", conn)
        if not deudas.empty:
            for _, r in deudas.iterrows():
                with st.expander(f"{r['nombre']} - {r['tipo']} ({r['concepto']})"):
                    p = st.text_input("Cobrar", value=str(r['monto_debe']-r['monto_pago']), key=f"p_{r['id']}")
                    if st.button("Confirmar", key=f"b_{r['id']}"):
                        cur.execute("UPDATE deudas SET monto_pago=?, pagado=?, fecha_cobro=? WHERE id=?", (r['monto_pago']+cl(p), 1, date.today(), r['id']))
                        conn.commit(); st.rerun()
        else: st.info("No hay cobros pendientes.")
    except Exception as e:
        st.error(f"Error en Sección 3: {e}")

# ==========================================
# SECCIÓN 4: MOROSOS
# ==========================================
if "4. Morosos" in menu:
    st.header("🚨 4. Morosos")
    try:
        dfm = pd.read_sql_query("SELECT inq.nombre, i.tipo, d.concepto, (d.monto_debe-d.monto_pago) as Saldo FROM deudas d JOIN contratos c ON d.id_contrato=c.id JOIN inmuebles i ON c.id_inmueble=i.id JOIN inquilinos inq ON c.id_inquilino=inq.id WHERE d.pagado=0", conn)
        st.table(dfm)
    except Exception as e:
        st.error(f"Error en Sección 4: {e}")

# ==========================================
# SECCIÓN 5: CAJA
# ==========================================
if "5. Caja" in menu:
    st.header("📊 5. Caja")
    try:
        dfc = pd.read_sql_query("SELECT fecha_cobro, concepto, monto_pago FROM deudas WHERE pagado=1", conn)
        st.dataframe(dfc, use_container_width=True)
    except Exception as e:
        st.error(f"Error en Sección 5: {e}")

# ==========================================
# SECCIÓN 6: MAESTROS
# ==========================================
if "6. Maestros" in menu:
    st.header("⚙️ 6. Maestros")
    try:
        t1, t2, t3 = st.tabs(["Inquilinos", "Bloques", "Unidades"])
        with t1:
            with st.form("f1"):
                n = st.text_input("Nombre"); d = st.text_input("DNI"); w = st.text_input("WhatsApp")
                if st.form_submit_button("Cargar"):
                    cur.execute("INSERT INTO inquilinos (nombre, dni, celular) VALUES (?,?,?)", (n, d, w))
                    conn.commit(); st.rerun()
            st.dataframe(pd.read_sql_query("SELECT id, nombre, dni FROM inquilinos", conn))
        with t2:
            nb = st.text_input("Nombre Bloque")
            if st.button("Guardar Bloque"):
                cur.execute("INSERT INTO bloques (nombre) VALUES (?)", (nb,))
                conn.commit(); st.rerun()
            st.table(pd.read_sql_query("SELECT * FROM bloques", conn))
        with t3:
            bls = pd.read_sql_query("SELECT * FROM bloques", conn)
            if not bls.empty:
                with st.form("f3"):
                    bid = st.selectbox("Bloque", bls['id'].tolist(), format_func=lambda x: bls[bls['id']==x]['nombre'].values[0])
                    tp = st.text_input("Unidad")
                    p1 = st.text_input("Alquiler"); p2 = st.text_input("Contrato"); p3 = st.text_input("Depósito")
                    if st.form_submit_button("Guardar Unidad"):
                        cur.execute("INSERT INTO inmuebles (id_bloque, tipo, precio_alquiler, costo_contrato, deposito_base) VALUES (?,?,?,?,?)", (bid, tp, cl(p1), cl(p2), cl(p3)))
                        conn.commit(); st.rerun()
            st.dataframe(pd.read_sql_query("SELECT i.id, b.nombre as Bloque, i.tipo as Unidad FROM inmuebles i JOIN bloques b ON i.id_bloque=b.id", conn))
    except Exception as e:
        st.error(f"Error en Sección 6: {e}")

conn.close()
