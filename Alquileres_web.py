import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, date, timedelta
import os
import io

# ==========================================
# 1. CORE: MOTOR DE DATOS (ARQUITECTURA SQL)
# ==========================================
DB_NAME = 'datos_alquileres.db'

def query_db(query, params=(), commit=False):
    with sqlite3.connect(DB_NAME, check_same_thread=False) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        cur = conn.cursor()
        if commit:
            cur.execute(query, params)
            conn.commit()
            return cur.lastrowid
        return pd.read_sql_query(query, conn, params=params)

def init_db():
    queries = [
        "CREATE TABLE IF NOT EXISTS bloques (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT UNIQUE)",
        "CREATE TABLE IF NOT EXISTS inquilinos (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT, dni TEXT, celular TEXT)",
        "CREATE TABLE IF NOT EXISTS inmuebles (id INTEGER PRIMARY KEY AUTOINCREMENT, id_bloque INTEGER, tipo TEXT, precio_alquiler INTEGER, costo_contrato INTEGER, deposito_base INTEGER, FOREIGN KEY(id_bloque) REFERENCES bloques(id) ON DELETE CASCADE)",
        "CREATE TABLE IF NOT EXISTS contratos (id INTEGER PRIMARY KEY AUTOINCREMENT, id_inmueble INTEGER, id_inquilino INTEGER, fecha_inicio DATE, fecha_fin DATE, monto_alquiler INTEGER, activo INTEGER DEFAULT 1, FOREIGN KEY(id_inmueble) REFERENCES inmuebles(id) ON DELETE CASCADE)",
        "CREATE TABLE IF NOT EXISTS deudas (id INTEGER PRIMARY KEY AUTOINCREMENT, id_contrato INTEGER, concepto TEXT, monto_debe INTEGER, monto_pago INTEGER DEFAULT 0, pagado INTEGER DEFAULT 1, fecha_pago DATE, FOREIGN KEY(id_contrato) REFERENCES contratos(id) ON DELETE CASCADE)"
    ]
    for q in queries: query_db(q, commit=True)

init_db()

# ==========================================
# 2. UI: NAVEGACIÓN Y ESTILOS
# ==========================================
st.set_page_config(page_title="NL Gestión Inmobiliaria", layout="wide")

with st.sidebar:
    st.title("🏠 NL PROPIEDADES")
    menu = st.radio("Menú Principal", ["Inventario", "Nuevo Contrato", "Cobranzas", "Morosos", "Reportes / Excel", "Configuración (Maestros)"])
    st.divider()
    if st.button("🚨 Limpiar Base de Datos"):
        if os.path.exists(DB_NAME): os.remove(DB_NAME); st.rerun()

# ==========================================
# 3. FUNCIONALIDADES OPERATIVAS
# ==========================================

if menu == "Inventario":
    st.header("Inventario de Unidades")
    df = query_db("""
        SELECT b.nombre as Bloque, i.tipo as Unidad, i.precio_alquiler, 
        CASE WHEN c.activo = 1 THEN '🔴 Ocupado' ELSE '🟢 Libre' END as Estado
        FROM inmuebles i 
        JOIN bloques b ON i.id_bloque = b.id
        LEFT JOIN contratos c ON i.id = c.id_inmueble AND c.activo = 1
    """)
    st.dataframe(df, use_container_width=True, hide_index=True)

elif menu == "Nuevo Contrato":
    st.header("Generación de Contrato")
    u_df = query_db("SELECT i.id, b.nombre || ' - ' || i.tipo as ref FROM inmuebles i JOIN bloques b ON i.id_bloque=b.id")
    i_df = query_db("SELECT id, nombre FROM inquilinos")
    
    if u_df.empty or i_df.empty:
        st.error("Primero cargue Inquilinos y Unidades en Configuración.")
    else:
        with st.form("alta_contrato"):
            c1, c2 = st.columns(2)
            u_id = c1.selectbox("Seleccione Unidad", u_df['id'], format_func=lambda x: u_df[u_df['id']==x]['ref'].values[0])
            i_id = c2.selectbox("Seleccione Inquilino", i_df['id'], format_func=lambda x: i_df[i_df['id']==x]['nombre'].values[0])
            f_ini = c1.date_input("Inicio de Contrato", date.today())
            meses = c2.number_input("Meses", 1, 60, 6)
            monto = st.number_input("Monto Alquiler Pactado", value=0)
            
            if st.form_submit_button("Confirmar Contrato"):
                f_fin = f_ini + timedelta(days=meses*30)
                cid = query_db("INSERT INTO contratos (id_inmueble, id_inquilino, fecha_inicio, fecha_fin, monto_alquiler) VALUES (?,?,?,?,?)", 
                               (u_id, i_id, f_ini, f_fin, monto), commit=True)
                # Generar primer cuota
                query_db("INSERT INTO deudas (id_contrato, concepto, monto_debe, pagado) VALUES (?, ?, ?, 0)", (cid, "Mes 1", monto), commit=True)
                st.success("Contrato generado correctamente."); st.rerun()

elif menu == "Cobranzas":
    st.header("Gestión de Cobros y Recibos")
    pendientes = query_db("""
        SELECT d.id, inq.nombre, i.tipo, d.concepto, d.monto_debe 
        FROM deudas d JOIN contratos c ON d.id_contrato=c.id 
        JOIN inquilinos inq ON c.id_inquilino=inq.id JOIN inmuebles i ON c.id_inmueble=i.id
        WHERE d.pagado = 0
    """)
    for _, r in pendientes.iterrows():
        with st.expander(f"Cobrar: {r['nombre']} - {r['tipo']} ({r['concepto']})"):
            if st.button(f"Confirmar Pago ${r['monto_debe']}", key=f"pay_{r['id']}"):
                query_db("UPDATE deudas SET pagado=1, fecha_pago=? WHERE id=?", (date.today(), r['id']), commit=True)
                st.success("Pago registrado."); st.rerun()

elif menu == "Morosos":
    st.header("Reporte de Deuda")
    morosos = query_db("""
        SELECT inq.nombre as Inquilino, i.tipo as Unidad, d.concepto, d.monto_debe as Deuda
        FROM deudas d JOIN contratos c ON d.id_contrato=c.id 
        JOIN inquilinos inq ON c.id_inquilino=inq.id JOIN inmuebles i ON c.id_inmueble=i.id
        WHERE d.pagado = 0
    """)
    st.table(morosos)

elif menu == "Reportes / Excel":
    st.header("Exportación de Datos")
    data = query_db("SELECT * FROM deudas WHERE pagado=1")
    if not data.empty:
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            data.to_excel(writer, index=False, sheet_name='Pagos')
        st.download_button("Descargar Reporte Excel", output.getvalue(), "Caja.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    else: st.info("No hay datos de caja para exportar.")

elif menu == "Configuración (Maestros)":
    st.header("Gestión de Maestros")
    t1, t2, t3 = st.tabs(["👤 Inquilinos", "🏢 Bloques", "🏠 Unidades"])
    
    with t1:
        with st.form("inq_form"):
            n, d, c = st.text_input("Nombre"), st.text_input("DNI"), st.text_input("WhatsApp")
            if st.form_submit_button("Añadir Inquilino"):
                query_db("INSERT INTO inquilinos (nombre, dni, celular) VALUES (?,?,?)", (n, d, c), commit=True); st.rerun()
        df_i = query_db("SELECT * FROM inquilinos")
        st.dataframe(df_i, use_container_width=True)
        if not df_i.empty:
            id_del = st.selectbox("Eliminar Inquilino (ID)", df_i['id'])
            if st.button("Eliminar Seleccionado"):
                query_db("DELETE FROM inquilinos WHERE id=?", (id_del,), commit=True); st.rerun()

    with t2:
        nb = st.text_input("Nombre del Bloque")
        if st.button("Añadir Bloque"):
            query_db("INSERT INTO bloques (nombre) VALUES (?)", (nb,), commit=True); st.rerun()
        df_b = query_db("SELECT * FROM bloques")
        st.table(df_b)

    with t3:
        bloques = query_db("SELECT * FROM bloques")
        if not bloques.empty:
            with st.form("uni_form"):
                b_id = st.selectbox("Bloque", bloques['id'], format_func=lambda x: bloques[bloques['id']==x]['nombre'].values[0])
                ut, pr = st.text_input("Unidad (Ej: Local 1)"), st.number_input("Alquiler Sugerido", value=0)
                if st.form_submit_button("Añadir Unidad"):
                    query_db("INSERT INTO inmuebles (id_bloque, tipo, precio_alquiler) VALUES (?,?,?)", (b_id, ut, pr), commit=True); st.rerun()
        st.dataframe(query_db("SELECT i.id, b.nombre as Bloque, i.tipo, i.precio_alquiler FROM inmuebles i JOIN bloques b ON i.id_bloque=b.id"), use_container_width=True)
