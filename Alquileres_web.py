import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, date, timedelta
import os
import urllib.parse

# 1. CONFIGURACIÓN
st.set_page_config(page_title="NL Propiedades", layout="wide", initial_sidebar_state="expanded")

# 2. BASE DE DATOS (CONEXIÓN SEGURA)
def conectar():
    return sqlite3.connect('datos_alquileres.db', check_same_thread=False, timeout=30)

conn = conectar()
cursor = conn.cursor()

# CREACIÓN ESTRUCTURA
cursor.execute("CREATE TABLE IF NOT EXISTS bloques (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT UNIQUE)")
cursor.execute("CREATE TABLE IF NOT EXISTS inmuebles (id INTEGER PRIMARY KEY AUTOINCREMENT, id_bloque INTEGER, tipo TEXT, precio_alquiler INTEGER, costo_contrato INTEGER, deposito_base INTEGER)")
cursor.execute("CREATE TABLE IF NOT EXISTS inquilinos (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT, celular TEXT, dni TEXT, direccion TEXT, emergencia_contacto TEXT, procedencia TEXT, grupo TEXT)")
cursor.execute("CREATE TABLE IF NOT EXISTS contratos (id INTEGER PRIMARY KEY AUTOINCREMENT, id_inmueble INTEGER, id_inquilino INTEGER, fecha_inicio DATE, fecha_fin DATE, meses INTEGER, activo INTEGER DEFAULT 1, monto_alquiler INTEGER, monto_contrato INTEGER, monto_deposito INTEGER)")
cursor.execute("CREATE TABLE IF NOT EXISTS deudas (id INTEGER PRIMARY KEY AUTOINCREMENT, id_contrato INTEGER, concepto TEXT, mes_anio TEXT, monto_debe INTEGER, monto_pago INTEGER DEFAULT 0, pagado INTEGER DEFAULT 0, fecha_cobro DATE)")
conn.commit()

# MIGRACIÓN DE COLUMNAS (PROTECCIÓN DE DATOS)
try:
    cursor.execute("ALTER TABLE inquilinos ADD COLUMN celular TEXT")
    cursor.execute("ALTER TABLE inquilinos ADD COLUMN dni TEXT")
    cursor.execute("ALTER TABLE inmuebles ADD COLUMN precio_alquiler INTEGER")
except: pass
conn.commit()

# 3. BARRA LATERAL (MENÚ CONSTANTE)
with st.sidebar:
    st.title("NL PROPIEDADES")
    menu = st.radio("Navegación:", ["1. Inventario", "2. Nuevo Contrato", "3. Cobranzas", "4. Morosos", "5. Caja", "6. Maestros"])
    st.divider()
    if st.button("🚨 RESET BASE (CUIDADO)"):
        os.remove('datos_alquileres.db')
        st.rerun()

# UTILIDADES
def f_mon(v): return f"$ {int(v or 0):,}".replace(",", ".")
def cl(t): return int(str(t).replace('$', '').replace('.', '').replace(',', '').strip() or 0)

# ==========================================
# SECCIÓN 1: INVENTARIO
# ==========================================
if "1. Inventario" in menu:
    st.header("🏠 1. Inventario")
    df = pd.read_sql_query("SELECT b.nombre as Bloque, i.tipo as Unidad, i.precio_alquiler, MAX(c.activo) as ocupado FROM inmuebles i JOIN bloques b ON i.id_bloque = b.id LEFT JOIN contratos c ON i.id = c.id_inmueble AND c.activo = 1 GROUP BY i.id", conn)
    if not df.empty:
        df['Estado'] = df['ocupado'].apply(lambda x: "🔴 OCUPADO" if x == 1 else "🟢 LIBRE")
        st.dataframe(df, use_container_width=True)
    else: st.info("Cargue datos en la Sección 6")

# ==========================================
# SECCIÓN 2: NUEVO CONTRATO
# ==========================================
if "2. Nuevo Contrato" in menu:
    st.header("📝 2. Nuevo Contrato")
    unid = pd.read_sql_query("SELECT i.id, b.nombre || ' - ' || i.tipo as ref, i.precio_alquiler, i.costo_contrato, i.deposito_base FROM inmuebles i JOIN bloques b ON i.id_bloque=b.id", conn)
    inqs = pd.read_sql_query("SELECT id, nombre FROM inquilinos", conn)
    if not unid.empty and not inqs.empty:
        with st.form("f_con"):
            u_sel = st.selectbox("Unidad", unid['id'].tolist(), format_func=lambda x: unid[unid['id']==x]['ref'].values[0])
            i_sel = st.selectbox("Inquilino", inqs['id'].tolist(), format_func=lambda x: inqs[inqs['id']==x]['nombre'].values[0])
            f_ini = st.date_input("Inicio", date.today())
            meses = st.number_input("Meses", 1, 60, 6)
            row = unid[unid['id']==u_sel].iloc[0]
            m1 = st.text_input("Alquiler", value=str(row['precio_alquiler']))
            m2 = st.text_input("Contrato", value=str(row['costo_contrato']))
            m3 = st.text_input("Depósito", value=str(row['deposito_base']))
            if st.form_submit_button("GRABAR"):
                cursor.execute("INSERT INTO contratos (id_inmueble, id_inquilino, fecha_inicio, fecha_fin, meses, monto_alquiler, monto_contrato, monto_deposito) VALUES (?,?,?,?,?,?,?,?)", (u_sel, i_sel, f_ini, f_ini + timedelta(days=meses*30), meses, cl(m1), cl(m2), cl(m3)))
                cid = cursor.lastrowid
                cursor.executemany("INSERT INTO deudas (id_contrato, concepto, mes_anio, monto_debe) VALUES (?,?,?,?)", [(cid, "Contrato", f_ini.strftime("%m/%y"), cl(m2)), (cid, "Depósito", f_ini.strftime("%m/%y"), cl(m3)), (cid, "Alquiler 1", f_ini.strftime("%m/%y"), cl(m1))])
                conn.commit(); st.success("¡Contrato Guardado!"); st.rerun()
    else: st.warning("Faltan Inquilinos o Unidades")

# ==========================================
# SECCIÓN 3: COBRANZAS
# ==========================================
if "3. Cobranzas" in menu:
    st.header("💰 3. Cobranzas")
    deu = pd.read_sql_query("SELECT d.id, inq.nombre, i.tipo, d.concepto, d.monto_debe, d.monto_pago FROM deudas d JOIN contratos c ON d.id_contrato=c.id JOIN inmuebles i ON c.id_inmueble=i.id JOIN inquilinos inq ON c.id_inquilino=inq.id WHERE d.pagado=0", conn)
    for _, r in deu.iterrows():
        with st.expander(f"{r['nombre']} - {r['tipo']} ({r['concepto']})"):
            m_p = st.text_input("Monto", value=str(r['monto_debe']-r['monto_pago']), key=r['id'])
            if st.button("Cobrar", key=f"b{r['id']}"):
                cursor.execute("UPDATE deudas SET monto_pago=?, pagado=?, fecha_cobro=? WHERE id=?", (r['monto_pago']+cl(m_p), 1, date.today(), r['id']))
                conn.commit(); st.rerun()

# ==========================================
# SECCIÓN 4: MOROSOS
# ==========================================
if "4. Morosos" in menu:
    st.header("🚨 4. Morosos")
    st.dataframe(pd.read_sql_query("SELECT inq.nombre, i.tipo, d.concepto, (d.monto_debe-d.monto_pago) as Saldo FROM deudas d JOIN contratos c ON d.id_contrato=c.id JOIN inmuebles i ON c.id_inmueble=i.id JOIN inquilinos inq ON c.id_inquilino=inq.id WHERE d.pagado=0", conn))

# ==========================================
# SECCIÓN 5: CAJA
# ==========================================
if "5. Caja" in menu:
    st.header("📊 5. Caja")
    st.dataframe(pd.read_sql_query("SELECT fecha_cobro, concepto, monto_pago FROM deudas WHERE pagado=1", conn))

# ==========================================
# SECCIÓN 6: MAESTROS
# ==========================================
if "6. Maestros" in menu:
    st.header("⚙️ 6. Maestros")
    t1, t2, t3 = st.tabs(["Inquilinos", "Bloques", "Unidades"])
    with t1:
        with st.form("fi"):
            n = st.text_input("Nombre"); d = st.text_input("DNI"); w = st.text_input("WhatsApp")
            if st.form_submit_button("Cargar"):
                cursor.execute("INSERT INTO inquilinos (nombre, dni, celular) VALUES (?,?,?)", (n, d, w))
                conn.commit(); st.rerun()
        st.dataframe(pd.read_sql_query("SELECT id, nombre, dni FROM inquilinos", conn))
    with t2:
        nb = st.text_input("Nombre Bloque")
        if st.button("Guardar Bloque"):
            cursor.execute("INSERT INTO bloques (nombre) VALUES (?)", (nb,))
            conn.commit(); st.rerun()
    with t3:
        bls = pd.read_sql_query("SELECT * FROM bloques", conn)
        if not bls.empty:
            with st.form("fu"):
                bid = st.selectbox("Bloque", bls['id'].tolist(), format_func=lambda x: bls[bls['id']==x]['nombre'].values[0])
                ut = st.text_input("Unidad")
                p1 = st.text_input("Alquiler Sugerido"); p2 = st.text_input("Contrato Sugerido"); p3 = st.text_input("Depósito Sugerido")
                if st.form_submit_button("Guardar Unidad"):
                    cursor.execute("INSERT INTO inmuebles (id_bloque, tipo, precio_alquiler, costo_contrato, deposito_base) VALUES (?,?,?,?,?)", (bid, ut, cl(p1), cl(p2), cl(p3)))
                    conn.commit(); st.rerun()
