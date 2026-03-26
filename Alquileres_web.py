import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, date, timedelta
import os
import io

# ==========================================
# 1. IDENTIDAD Y CONFIGURACIÓN (V.2.4)
# ==========================================
st.set_page_config(page_title="NL PROPIEDADES - V.2.4", layout="wide")
st.cache_data.clear()

st.markdown("""
    <style>
    .stButton>button { background-color: #D4AF37; color: black; font-weight: bold; width: 100%; border-radius: 5px; }
    h1, h2, h3, h4 { color: #D4AF37; }
    [data-testid="stSidebar"] { background-color: #111; border-right: 1px solid #D4AF37; }
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 2. MOTOR DE DATOS
# ==========================================
def db_query(sql, params=(), commit=False):
    try:
        with sqlite3.connect('datos_alquileres.db', check_same_thread=False) as conn:
            if commit:
                cur = conn.cursor()
                cur.execute(sql, params)
                conn.commit()
                return cur.lastrowid
            return pd.read_sql_query(sql, conn, params=params)
    except Exception as e:
        st.error(f"Error de base de datos: {e}")
        return None

# Inicialización de Tablas
db_query("CREATE TABLE IF NOT EXISTS bloques (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT UNIQUE)", commit=True)
db_query("""CREATE TABLE IF NOT EXISTS inquilinos (
    id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT, dni TEXT, celular TEXT, 
    emergencia TEXT, procedencia TEXT, grupo TEXT)""", commit=True)
db_query("CREATE TABLE IF NOT EXISTS inmuebles (id INTEGER PRIMARY KEY AUTOINCREMENT, id_bloque INTEGER, tipo TEXT, precio_alquiler INTEGER, costo_contrato INTEGER, deposito_base INTEGER)", commit=True)
db_query("CREATE TABLE IF NOT EXISTS contratos (id INTEGER PRIMARY KEY AUTOINCREMENT, id_inmueble INTEGER, id_inquilino INTEGER, fecha_inicio DATE, fecha_fin DATE, monto_alquiler INTEGER, activo INTEGER DEFAULT 1)", commit=True)
db_query("CREATE TABLE IF NOT EXISTS deudas (id INTEGER PRIMARY KEY AUTOINCREMENT, id_contrato INTEGER, concepto TEXT, monto_debe INTEGER, monto_pago INTEGER DEFAULT 0, pagado INTEGER DEFAULT 0, fecha_pago DATE)", commit=True)

# --- FUNCIONES DE FORMATO ---
def cl(t): return int(str(t).replace('$', '').replace('.', '').replace(',', '').strip() or 0)
def f_m(v): return f"{int(v or 0):,}".replace(",", ".")

# ==========================================
# 3. BARRA LATERAL
# ==========================================
with st.sidebar:
    if os.path.exists("alquileres.jpg"): st.image("alquileres.jpg", use_container_width=True)
    else: st.title("🏠 NL PROPIEDADES")
    
    st.info("🚀 VERSIÓN: V.2.4 - REVISIÓN FINAL")
    menu = st.radio("MENÚ:", ["🏠 Inventario", "📝 Nuevo Contrato", "💰 Cobranzas", "📊 Caja y Reportes", "⚙️ Maestros"])
    
    if st.button("🚨 RESET BASE (CUIDADO)"):
        if os.path.exists('datos_alquileres.db'): os.remove('datos_alquileres.db')
        st.rerun()

# ==========================================
# 4. SECCIONES
# ==========================================

# --- 1. INVENTARIO ---
if menu == "🏠 Inventario":
    st.header("Inventario de Unidades y Disponibilidad")
    query_inv = """
        SELECT b.nombre as Bloque, i.tipo as Unidad, i.precio_alquiler as [Alquiler Sug.],
               i.costo_contrato as [Gasto Cont.], i.deposito_base as [Depósito Sug.],
               CASE WHEN c.activo = 1 THEN '🔴 OCUPADO' ELSE '🟢 LIBRE' END as Estado,
               CASE WHEN c.activo = 1 THEN c.fecha_fin ELSE 'DISPONIBLE HOY' END as [Vence/Libre]
        FROM inmuebles i JOIN bloques b ON i.id_bloque = b.id
        LEFT JOIN contratos c ON i.id = c.id_inmueble AND c.activo = 1
    """
    df = db_query(query_inv)
    if df is not None and not df.empty:
        for col in ['Alquiler Sug.', 'Gasto Cont.', 'Depósito Sug.']:
            df[col] = df[col].apply(f_m)
        st.dataframe(df, use_container_width=True, hide_index=True)
    else: st.info("Cargue datos en Maestros.")

# --- 2. NUEVO CONTRATO ---
elif menu == "📝 Nuevo Contrato":
    st.header("Generar Nuevo Contrato")
    u_df = db_query("SELECT i.id, b.nombre || ' - ' || i.tipo as ref, i.precio_alquiler, i.costo_contrato, i.deposito_base FROM inmuebles i JOIN bloques b ON i.id_bloque=b.id")
    i_df = db_query("SELECT id, nombre FROM inquilinos")
    
    if u_df is not None and i_df is not None and not u_df.empty and not i_df.empty:
        with st.form("f_con", clear_on_submit=True):
            c1, c2 = st.columns(2)
            u_id = c1.selectbox("Unidad", u_df['id'], format_func=lambda x: u_df[u_df['id']==x]['ref'].values[0])
            i_id = c2.selectbox("Inquilino", i_df['id'], format_func=lambda x: i_df[i_df['id']==x]['nombre'].values[0])
            f_ini = c1.date_input("Fecha Inicio", date.today())
            meses = c2.number_input("Meses", 1, 60, 6)
            
            row = u_df[u_df['id']==u_id].iloc[0]
            m1 = c1.text_input("Monto Alquiler", value=f_m(row['precio_alquiler']))
            m2 = c2.text_input("Gasto Contrato", value=f_m(row['costo_contrato']))
            m3 = st.text_input("Depósito", value=f_m(row['deposito_base']))
            
            if st.form_submit_button("GRABAR CONTRATO"):
                f_fin = f_ini + timedelta(days=meses*30)
                cid = db_query("INSERT INTO contratos (id_inmueble, id_inquilino, fecha_inicio, fecha_fin, monto_alquiler) VALUES (?,?,?,?,?)", 
                               (u_id, i_id, f_ini, f_fin, cl(m1)), commit=True)
                db_query("INSERT INTO deudas (id_contrato, concepto, monto_debe) VALUES (?, 'Contrato', ?)", (cid, cl(m2)), commit=True)
                db_query("INSERT INTO deudas (id_contrato, concepto, monto_debe) VALUES (?, 'Depósito', ?)", (cid, cl(m3)), commit=True)
                db_query("INSERT INTO deudas (id_contrato, concepto, monto_debe) VALUES (?, 'Mes 1', ?)", (cid, cl(m1)), commit=True)
                st.success(f"✅ Contrato {cid} creado exitosamente.")
                st.code(f"COMPROBANTE ALTA NL\nID: {cid}\nInquilino: {i_id}\nUnidad: {u_id}\nAlquiler: $ {m1}\nVence: {f_fin}")
    else: st.warning("Cargue datos previos en Maestros.")

# --- 3. COBRANZAS ---
elif menu == "💰 Cobranzas":
    st.header("Cobros Pendientes")
    deu = db_query("""
        SELECT d.id, inq.nombre, i.tipo, d.concepto, d.monto_debe 
        FROM deudas d JOIN contratos c ON d.id_contrato=c.id 
        JOIN inmuebles i ON c.id_inmueble=i.id JOIN inquilinos inq ON c.id_inquilino=inq.id 
        WHERE d.pagado=0
    """)
    if deu is not None and not deu.empty:
        for _, r in deu.iterrows():
            with st.expander(f"{r['nombre']} - {r['tipo']} (${f_m(r['monto_debe'])})"):
                if st.button(f"Confirmar Cobro: {r['concepto']}", key=f"b_{r['id']}"):
                    db_query("UPDATE deudas SET pagado=1, fecha_pago=?, monto_pago=? WHERE id=?", (date.today(), r['monto_debe'], r['id']), commit=True)
                    st.rerun()
    else: st.info("Sin deudas pendientes.")

# --- 4. CAJA Y REPORTES ---
elif menu == "📊 Caja y Reportes":
    st.header("Reporte de Caja")
    df_c = db_query("""
        SELECT d.fecha_pago, inq.nombre as Inquilino, d.concepto, d.monto_pago 
        FROM deudas d JOIN contratos c ON d.id_contrato=c.id
        JOIN inquilinos inq ON c.id_inquilino=inq.id WHERE d.pagado=1
    """)
    if df_c is not None and not df_c.empty:
        df_c['fecha_pago'] = pd.to_datetime(df_c['fecha_pago'])
        c1, c2 = st.columns(2)
        m = c1.selectbox("Mes", range(1,13), index=date.today().month-1)
        a = c2.selectbox("Año", [2025, 2026], index=1)
        
        filtro = df_c[(df_c['fecha_pago'].dt.month == m) & (df_c['fecha_pago'].dt.year == a)].copy()
        st.metric("Recaudación del Período", f"$ {f_m(filtro['monto_pago'].sum())}")
        filtro['monto_pago'] = filtro['monto_pago'].apply(f_m)
        st.dataframe(filtro, use_container_width=True, hide_index=True)
    else: st.info("No hay pagos registrados.")

# --- 5. MAESTROS ---
elif menu == "⚙️ Maestros":
    t1, t2, t3, t4 = st.tabs(["Inquilinos", "Unidades", "Bloques", "Contratos Activos"])
    
    with t1:
        with st.form("fi", clear_on_submit=True):
            c1, c2 = st.columns(2)
            n = c1.text_input("Nombre"); d = c1.text_input("DNI"); cel = c1.text_input("WhatsApp")
            pro = c2.text_input("Procedencia"); gru = c2.text_input("Grupo"); eme = c2.text_input("Emergencia")
            if st.form_submit_button("Guardar"):
                db_query("INSERT INTO inquilinos (nombre, dni, celular, emergencia, procedencia, grupo) VALUES (?,?,?,?,?,?)", (n, d, cel, eme, pro, gru), commit=True); st.rerun()
        st.dataframe(db_query("SELECT * FROM inquilinos"), use_container_width=True)

    with t2:
        bls = db_query("SELECT * FROM bloques")
        with st.form("fu"):
            bid = st.selectbox("Bloque", bls['id'].tolist(), format_func=lambda x: bls[bls['id']==x]['nombre'].values[0]) if not bls.empty else st.write("Cargue bloques")
            ut = st.text_input("Nombre Unidad"); p1 = st.text_input("Alquiler Sug."); p2 = st.text_input("Contrato Sug."); p3 = st.text_input("Depósito Sug.")
            if st.form_submit_button("Crear Unidad"):
                db_query("INSERT INTO inmuebles (id_bloque, tipo, precio_alquiler, costo_contrato, deposito_base) VALUES (?,?,?,?,?)", (bid, ut, cl(p1), cl(p2), cl(p3)), commit=True); st.rerun()
        
        st.write("---")
        id_e = st.number_input("ID Unidad para EDITAR o BORRAR", step=1, value=0)
        if id_e > 0:
            u_dat = db_query(f"SELECT * FROM inmuebles WHERE id={id_e}")
            if not u_dat.empty:
                new_p = st.text_input("Nuevo Alquiler Sugerido", value=f_m(u_dat['precio_alquiler'].iloc[0]))
                if st.button("Actualizar Precio"): db_query(f"UPDATE inmuebles SET precio_alquiler={cl(new_p)} WHERE id={id_e}", commit=True); st.rerun()
                if st.button("🗑️ Eliminar Unidad"): db_query(f"DELETE FROM inmuebles WHERE id={id_e}", commit=True); st.rerun()

    with t3:
        nb = st.text_input("Nuevo Bloque")
        if st.button("Guardar Bloque"): db_query("INSERT INTO bloques (nombre) VALUES (?)", (nb,), commit=True); st.rerun()
        st.table(db_query("SELECT * FROM bloques"))

    with t4:
        df_con = db_query("""
            SELECT c.id, inq.nombre as Inquilino, i.tipo as Unidad, c.fecha_fin as Vencimiento 
            FROM contratos c JOIN inquilinos inq ON c.id_inquilino=inq.id JOIN inmuebles i ON c.id_inmueble=i.id
        """)
        st.dataframe(df_con, use_container_width=True, hide_index=True)
        idc = st.number_input("ID Contrato a borrar", step=1, value=0)
        if st.button("🗑️ Eliminar Contrato"): db_query(f"DELETE FROM contratos WHERE id={idc}", commit=True); st.rerun()
