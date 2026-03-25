import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, date, timedelta
import os
import io

# ==========================================
# 1. IDENTIDAD Y CONFIGURACIÓN (V.2.3)
# ==========================================
st.set_page_config(page_title="NL PROPIEDADES - V.2.3", layout="wide")
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
    with sqlite3.connect('datos_alquileres.db', check_same_thread=False) as conn:
        if commit:
            cur = conn.cursor()
            cur.execute(sql, params)
            conn.commit()
            return cur.lastrowid
        return pd.read_sql_query(sql, conn, params=params)

# Inicialización con nuevos campos
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
    
    st.info("🚀 VERSIÓN: V.2.3 - FULL")
    menu = st.radio("MENÚ:", ["🏠 Inventario", "📝 Nuevo Contrato", "💰 Cobranzas", "📊 Caja y Filtros", "⚙️ Maestros"])
    
    if st.button("🚨 RESET BASE"):
        if os.path.exists('datos_alquileres.db'): os.remove('datos_alquileres.db')
        st.rerun()

# ==========================================
# 4. SECCIONES
# ==========================================

# --- 1. INVENTARIO ---
if menu == "🏠 Inventario":
    st.header("Inventario de Unidades")
    df = db_query("""
        SELECT b.nombre as Bloque, i.tipo as Unidad, i.precio_alquiler, i.costo_contrato, i.deposito_base,
        CASE WHEN c.activo = 1 THEN '🔴 OCUPADO' ELSE '🟢 LIBRE' END as Estado,
        CASE WHEN c.activo = 1 THEN c.fecha_fin ELSE 'HOY' END as [Disponible]
        FROM inmuebles i JOIN bloques b ON i.id_bloque = b.id
        LEFT JOIN contratos c ON i.id = c.id_inmueble AND c.activo = 1
    """)
    if not df.empty:
        # Formatear importes en el DataFrame
        for col in ['precio_alquiler', 'costo_contrato', 'deposito_base']:
            df[col] = df[col].apply(f_m)
        st.dataframe(df, use_container_width=True, hide_index=True)

# --- 2. NUEVO CONTRATO ---
elif menu == "📝 Nuevo Contrato":
    st.header("Nuevo Contrato")
    u_df = db_query("SELECT i.id, b.nombre || ' - ' || i.tipo as ref, i.precio_alquiler, i.costo_contrato, i.deposito_base FROM inmuebles i JOIN bloques b ON i.id_bloque=b.id")
    i_df = db_query("SELECT id, nombre FROM inquilinos")
    
    if not u_df.empty and not i_df.empty:
        with st.form("f_con", clear_on_submit=True):
            c1, c2 = st.columns(2)
            u_id = c1.selectbox("Unidad", u_df['id'], format_func=lambda x: u_df[u_df['id']==x]['ref'].values[0])
            i_id = c2.selectbox("Inquilino", i_df['id'], format_func=lambda x: i_df[i_df['id']==x]['nombre'].values[0])
            f_ini = c1.date_input("Inicio", date.today())
            meses = c2.number_input("Meses", 1, 60, 6)
            
            row = u_df[u_df['id']==u_id].iloc[0]
            m1 = c1.text_input("Alquiler", value=f_m(row['precio_alquiler']))
            m2 = c2.text_input("Gasto Contrato", value=f_m(row['costo_contrato']))
            m3 = st.text_input("Depósito", value=f_m(row['deposito_base']))
            
            if st.form_submit_button("GRABAR Y GENERAR DOCUMENTO"):
                f_fin = f_ini + timedelta(days=meses*30)
                cid = db_query("INSERT INTO contratos (id_inmueble, id_inquilino, fecha_inicio, fecha_fin, monto_alquiler) VALUES (?,?,?,?,?)", (u_id, i_id, f_ini, f_fin, cl(m1)), commit=True)
                db_query("INSERT INTO deudas (id_contracto, concepto, monto_debe) VALUES (?, 'Contrato', ?)", (cid, cl(m2)), commit=True)
                db_query("INSERT INTO deudas (id_contrato, concepto, monto_debe) VALUES (?, 'Depósito', ?)", (cid, cl(m3)), commit=True)
                db_query("INSERT INTO deudas (id_contrato, concepto, monto_debe) VALUES (?, 'Mes 1', ?)", (cid, cl(m1)), commit=True)
                
                st.success("✅ Contrato Grabado")
                # Documento de Resumen
                st.subheader("📄 Resumen de Contrato (Para Copiar)")
                resumen = f"""
                PROPIEDADES NL - COMPROBANTE DE ALTA
                ------------------------------------
                ID Contrato: {cid} | Fecha: {date.today()}
                Inquilino ID: {i_id}
                Unidad: {u_id}
                Periodo: {f_ini} hasta {f_fin}
                Alquiler Pactado: $ {m1}
                ------------------------------------
                """
                st.code(resumen)

# --- 3. COBRANZAS ---
elif menu == "💰 Cobranzas":
    st.header("Cobranzas")
    deu = db_query("SELECT d.id, inq.nombre, i.tipo, d.concepto, d.monto_debe FROM deudas d JOIN contratos c ON d.id_contrato=c.id JOIN inmuebles i ON c.id_inmueble=i.id JOIN inquilinos inq ON c.id_inquilino=inq.id WHERE d.pagado=0")
    for _, r in deu.iterrows():
        with st.expander(f"{r['nombre']} - {r['tipo']} (${f_m(r['monto_debe'])})"):
            if st.button(f"Cobrar {r['concepto']}", key=f"b_{r['id']}"):
                db_query("UPDATE deudas SET pagado=1, fecha_pago=?, monto_pago=? WHERE id=?", (date.today(), r['monto_debe'], r['id']), commit=True)
                st.rerun()

# --- 4. CAJA Y FILTROS ---
elif menu == "📊 Caja y Filtros":
    st.header("Reporte de Caja")
    df_c = db_query("SELECT fecha_pago, concepto, monto_pago FROM deudas WHERE pagado=1")
    if not df_c.empty:
        df_c['fecha_pago'] = pd.to_datetime(df_c['fecha_pago'])
        c1, c2 = st.columns(2)
        mes = c1.selectbox("Mes", range(1,13), index=date.today().month-1)
        anio = c2.selectbox("Año", [2025, 2026], index=1)
        
        filtro = df_c[(df_c['fecha_pago'].dt.month == mes) & (df_c['fecha_pago'].dt.year == anio)]
        st.metric("Total del Periodo", f"$ {f_m(filtro['monto_pago'].sum())}")
        st.dataframe(filtro, use_container_width=True)

# --- 5. MAESTROS (EDICIÓN Y CAMPOS EXTRA) ---
elif menu == "⚙️ Maestros":
    t1, t2, t3 = st.tabs(["👤 Inquilinos", "🏠 Unidades", "🏢 Bloques"])
    
    with t1:
        with st.form("fi", clear_on_submit=True):
            col1, col2 = st.columns(2)
            n = col1.text_input("Nombre"); d = col1.text_input("DNI"); cel = col1.text_input("WhatsApp")
            pro = col2.text_input("Procedencia"); gru = col2.text_input("Grupo/Referencia"); eme = col2.text_input("Emergencia (Nombre/Tel)")
            if st.form_submit_button("Guardar"):
                db_query("INSERT INTO inquilinos (nombre, dni, celular, emergencia, procedencia, grupo) VALUES (?,?,?,?,?,?)", (n, d, cel, eme, pro, gru), commit=True); st.rerun()
        st.dataframe(db_query("SELECT * FROM inquilinos"), use_container_width=True)

    with t2:
        st.subheader("Gestión de Unidades")
        bls = db_query("SELECT * FROM bloques")
        with st.form("fu"):
            bid = st.selectbox("Bloque", bls['id'].tolist(), format_func=lambda x: bls[bls['id']==x]['nombre'].values[0])
            ut = st.text_input("Nombre Unidad"); p1 = st.text_input("Alquiler Sug."); p2 = st.text_input("Contrato Sug."); p3 = st.text_input("Depósito Sug.")
            if st.form_submit_button("Crear Unidad"):
                db_query("INSERT INTO inmuebles (id_bloque, tipo, precio_alquiler, costo_contrato, deposito_base) VALUES (?,?,?,?,?)", (bid, ut, cl(p1), cl(p2), cl(p3)), commit=True); st.rerun()
        
        st.write("---")
        st.subheader("Edición de Unidad existente")
        edit_id = st.number_input("ID de Unidad a editar", step=1, value=0)
        if edit_id > 0:
            u_data = db_query(f"SELECT * FROM inmuebles WHERE id={edit_id}")
            if not u_data.empty:
                new_p = st.text_input("Nuevo Alquiler Sugerido", value=f_m(u_data['precio_alquiler'].iloc[0]))
                if st.button("Actualizar Precio"):
                    db_query(f"UPDATE inmuebles SET precio_alquiler={cl(new_p)} WHERE id={edit_id}", commit=True); st.success("Actualizado"); st.rerun()
