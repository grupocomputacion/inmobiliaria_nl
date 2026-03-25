import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, date, timedelta
import os
import io

# ==========================================
# 1. IDENTIFICACIÓN VISUAL FORZADA (V.1.1)
# ==========================================
st.set_page_config(page_title="NL PROPIEDADES - V.1.1", layout="wide")

# Barra Lateral con Logo y Versión
with st.sidebar:
    st.error("🚀 VERSIÓN ACTUAL: V.1.1") # Cartel rojo para que lo veas sí o sí
    if os.path.exists("alquileres.jpg"):
        st.image("alquileres.jpg", use_container_width=True)
    else:
        st.title("🏠 NL PROPIEDADES")
    
    st.write("---")
    menu = st.radio("SECCIONES:", 
                    ["1. Inventario", "2. Nuevo Contrato", "3. Cobranzas", "4. Morosos", "5. Reportes Excel", "6. Maestros (ABM)"])
    st.write("---")
    if st.button("🚨 BORRAR TODO"):
        if os.path.exists('datos_alquileres.db'):
            os.remove('datos_alquileres.db')
            st.rerun()

# ==========================================
# 2. BASE DE DATOS
# ==========================================
def db_query(sql, params=(), commit=False):
    with sqlite3.connect('datos_alquileres.db', check_same_thread=False) as conn:
        if commit:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            conn.commit()
            return cursor.lastrowid
        return pd.read_sql_query(sql, conn, params=params)

# Inicializar Tablas
db_query("CREATE TABLE IF NOT EXISTS bloques (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT UNIQUE)", commit=True)
db_query("CREATE TABLE IF NOT EXISTS inquilinos (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT, dni TEXT, celular TEXT)", commit=True)
db_query("CREATE TABLE IF NOT EXISTS inmuebles (id INTEGER PRIMARY KEY AUTOINCREMENT, id_bloque INTEGER, tipo TEXT, precio_alquiler INTEGER, costo_contrato INTEGER, deposito_base INTEGER)", commit=True)
db_query("CREATE TABLE IF NOT EXISTS contratos (id INTEGER PRIMARY KEY AUTOINCREMENT, id_inmueble INTEGER, id_inquilino INTEGER, fecha_inicio DATE, fecha_fin DATE, monto_alquiler INTEGER, activo INTEGER DEFAULT 1)", commit=True)
db_query("CREATE TABLE IF NOT EXISTS deudas (id INTEGER PRIMARY KEY AUTOINCREMENT, id_contrato INTEGER, concepto TEXT, monto_debe INTEGER, monto_pago INTEGER DEFAULT 0, pagado INTEGER DEFAULT 0, fecha_pago DATE)", commit=True)

# --- UTILIDADES ---
def cl(t): return int(str(t).replace('$', '').replace('.', '').replace(',', '').strip() or 0)

# ==========================================
# 3. LÓGICA DE SECCIONES (IF PLANOS)
# ==========================================

if menu == "1. Inventario":
    st.header("🏠 Inventario Actual")
    df = db_query("SELECT b.nombre as Bloque, i.tipo as Unidad, i.precio_alquiler FROM inmuebles i JOIN bloques b ON i.id_bloque = b.id")
    st.dataframe(df, use_container_width=True)

if menu == "2. Nuevo Contrato":
    st.header("📝 Alta de Alquiler")
    u_df = db_query("SELECT i.id, b.nombre || ' - ' || i.tipo as ref, i.precio_alquiler, i.costo_contrato, i.deposito_base FROM inmuebles i JOIN bloques b ON i.id_bloque=b.id")
    i_df = db_query("SELECT id, nombre FROM inquilinos")
    if not u_df.empty and not i_df.empty:
        with st.form("f_con"):
            sel_u = st.selectbox("Unidad", u_df['id'], format_func=lambda x: u_df[u_df['id']==x]['ref'].values[0])
            sel_i = st.selectbox("Inquilino", i_df['id'], format_func=lambda x: i_df[i_df['id']==x]['nombre'].values[0])
            f_ini = st.date_input("Inicio", date.today())
            m1 = st.text_input("Alquiler", value=str(u_df[u_df['id']==sel_u]['precio_alquiler'].values[0]))
            if st.form_submit_button("GRABAR"):
                cid = db_query("INSERT INTO contratos (id_inmueble, id_inquilino, fecha_inicio, monto_alquiler) VALUES (?,?,?,?)", (sel_u, sel_i, f_ini, cl(m1)), commit=True)
                db_query("INSERT INTO deudas (id_contrato, concepto, monto_debe) VALUES (?, 'Mes 1', ?)", (cid, cl(m1)), commit=True)
                st.success("Contrato Generado")
    else: st.warning("Cargue datos en Maestros")

if menu == "3. Cobranzas":
    st.header("💰 Cobranzas")
    deu = db_query("SELECT d.id, inq.nombre, i.tipo, d.concepto, d.monto_debe FROM deudas d JOIN contratos c ON d.id_contrato=c.id JOIN inmuebles i ON c.id_inmueble=i.id JOIN inquilinos inq ON c.id_inquilino=inq.id WHERE d.pagado=0")
    for _, r in deu.iterrows():
        with st.expander(f"{r['nombre']} - {r['tipo']}"):
            if st.button(f"Cobrar ${r['monto_debe']}", key=f"b_{r['id']}"):
                db_query("UPDATE deudas SET pagado=1, fecha_pago=?, monto_pago=? WHERE id=?", (date.today(), r['monto_debe'], r['id']), commit=True)
                st.rerun()

if menu == "4. Morosos":
    st.header("🚨 Morosos")
    st.table(db_query("SELECT inq.nombre, d.monto_debe as Deuda FROM deudas d JOIN contratos c ON d.id_contrato=c.id JOIN inquilinos inq ON c.id_inquilino=inq.id WHERE d.pagado=0"))

if menu == "5. Reportes Excel":
    st.header("📊 Caja y Excel")
    df_c = db_query("SELECT fecha_pago as Fecha, concepto, monto_pago FROM deudas WHERE pagado=1")
    if not df_c.empty:
        st.dataframe(df_c)
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df_c.to_excel(writer, index=False)
        st.download_button("Descargar Excel", output.getvalue(), "Caja.xlsx")

if menu == "6. Maestros (ABM)":
    st.header("⚙️ Maestros")
    t1, t2, t3 = st.tabs(["Inquilinos", "Bloques", "Unidades"])
    with t1:
        n = st.text_input("Nombre")
        if st.button("Guardar Inquilino"):
            db_query("INSERT INTO inquilinos (nombre) VALUES (?)", (n,), commit=True); st.rerun()
        st.dataframe(db_query("SELECT * FROM inquilinos"))
    with t2:
        nb = st.text_input("Bloque")
        if st.button("Guardar Bloque"):
            db_query("INSERT INTO bloques (nombre) VALUES (?)", (nb,), commit=True); st.rerun()
    with t3:
        bls = db_query("SELECT * FROM bloques")
        if not bls.empty:
            bid = st.selectbox("Bloque", bls['id'], format_func=lambda x: bls[bls['id']==x]['nombre'].values[0])
            ut = st.text_input("Unidad")
            pr = st.text_input("Precio Sugerido")
            if st.button("Guardar Unidad"):
                db_query("INSERT INTO inmuebles (id_bloque, tipo, precio_alquiler) VALUES (?,?,?)", (bid, ut, cl(pr)), commit=True); st.rerun()
