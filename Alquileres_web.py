import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, date, timedelta
import os
import io

# ==========================================
# 1. IDENTIDAD Y CONTROL DE VERSIÓN (V.2.2)
# ==========================================
st.set_page_config(page_title="NL PROPIEDADES - V.2.2", layout="wide")

# Forzar limpieza de caché para evitar que el navegador muestre versiones viejas
st.cache_data.clear()

# Estilos Dorado/Negro NL
st.markdown("""
    <style>
    .stButton>button { background-color: #D4AF37; color: black; font-weight: bold; width: 100%; border-radius: 5px; }
    h1, h2, h3, h4 { color: #D4AF37; }
    [data-testid="stSidebar"] { background-color: #111; border-right: 1px solid #D4AF37; }
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 2. MOTOR DE DATOS (ESTRUCTURA COMPLETA)
# ==========================================
def db_query(sql, params=(), commit=False):
    with sqlite3.connect('datos_alquileres.db', check_same_thread=False) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        if commit:
            cur = conn.cursor()
            cur.execute(sql, params)
            conn.commit()
            return cur.lastrowid
        return pd.read_sql_query(sql, conn, params=params)

# Inicialización de Tablas e Integridad
db_query("CREATE TABLE IF NOT EXISTS bloques (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT UNIQUE)", commit=True)
db_query("CREATE TABLE IF NOT EXISTS inquilinos (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT, dni TEXT, celular TEXT)", commit=True)
db_query("CREATE TABLE IF NOT EXISTS inmuebles (id INTEGER PRIMARY KEY AUTOINCREMENT, id_bloque INTEGER, tipo TEXT, precio_alquiler INTEGER, costo_contrato INTEGER, deposito_base INTEGER, FOREIGN KEY(id_bloque) REFERENCES bloques(id) ON DELETE CASCADE)", commit=True)
db_query("CREATE TABLE IF NOT EXISTS contratos (id INTEGER PRIMARY KEY AUTOINCREMENT, id_inmueble INTEGER, id_inquilino INTEGER, fecha_inicio DATE, fecha_fin DATE, monto_alquiler INTEGER, activo INTEGER DEFAULT 1, FOREIGN KEY(id_inmueble) REFERENCES inmuebles(id) ON DELETE CASCADE)", commit=True)
db_query("CREATE TABLE IF NOT EXISTS deudas (id INTEGER PRIMARY KEY AUTOINCREMENT, id_contrato INTEGER, concepto TEXT, monto_debe INTEGER, monto_pago INTEGER DEFAULT 0, pagado INTEGER DEFAULT 0, fecha_pago DATE, FOREIGN KEY(id_contrato) REFERENCES contratos(id) ON DELETE CASCADE)", commit=True)

# Utilidades de conversión
def cl(t): return int(str(t).replace('$', '').replace('.', '').replace(',', '').strip() or 0)
def f_m(v): return f"$ {int(v or 0):,}".replace(",", ".")

# ==========================================
# 3. BARRA LATERAL (LOGO, MENÚ Y VERSIÓN)
# ==========================================
with st.sidebar:
    # 1. Recuperación del Logo
    if os.path.exists("alquileres.jpg"):
        st.image("alquileres.jpg", use_container_width=True)
    else:
        st.title("🏠 NL PROPIEDADES")
    
    # 2. Marcador de Versión para validación en GitHub
    st.info("🚀 VERSIÓN: V.2.2 - PRODUCCIÓN")
    
    st.write("---")
    menu = st.radio("NAVEGACIÓN:", 
                    ["🏠 Inventario", "📝 Nuevo Contrato", "💰 Cobranzas", "🚨 Morosos", "📊 Caja y Excel", "⚙️ Maestros"])
    
    st.write("---")
    if st.button("🚨 RESETEAR TODA LA BASE"):
        if os.path.exists('datos_alquileres.db'):
            os.remove('datos_alquileres.db')
            st.rerun()

# ==========================================
# 4. FUNCIONALIDADES POR SECCIÓN
# ==========================================

# --- SECCIÓN 1: INVENTARIO (CON ESTADO Y FECHAS) ---
if menu == "🏠 Inventario":
    st.header("Inventario y Disponibilidad de Unidades")
    query = """
        SELECT b.nombre as Bloque, i.tipo as Unidad, i.precio_alquiler as Alquiler, 
               i.costo_contrato as Contrato, i.deposito_base as Deposito,
               CASE WHEN c.activo = 1 THEN '🔴 OCUPADO' ELSE '🟢 LIBRE' END as Estado,
               CASE WHEN c.activo = 1 THEN c.fecha_fin ELSE 'DISPONIBLE HOY' END as [Disponible desde]
        FROM inmuebles i 
        JOIN bloques b ON i.id_bloque = b.id
        LEFT JOIN contratos c ON i.id = c.id_inmueble AND c.activo = 1
    """
    df = db_query(query)
    if not df.empty:
        st.dataframe(df, use_container_width=True, hide_index=True)
    else: st.info("No hay unidades cargadas. Diríjase a Maestros.")

# --- SECCIÓN 2: NUEVO CONTRATO ---
elif menu == "📝 Nuevo Contrato":
    st.header("Generar Nuevo Contrato de Alquiler")
    u_df = db_query("SELECT i.id, b.nombre || ' - ' || i.tipo as ref, i.precio_alquiler, i.costo_contrato, i.deposito_base FROM inmuebles i JOIN bloques b ON i.id_bloque=b.id")
    i_df = db_query("SELECT id, nombre FROM inquilinos")
    
    if not u_df.empty and not i_df.empty:
        with st.form("f_contrato", clear_on_submit=True):
            c1, c2 = st.columns(2)
            u_id = c1.selectbox("Seleccione Unidad", u_df['id'].tolist(), format_func=lambda x: u_df[u_df['id']==x]['ref'].values[0])
            i_id = c2.selectbox("Seleccione Inquilino", i_df['id'].tolist(), format_func=lambda x: i_df[i_df['id']==x]['nombre'].values[0])
            f_ini = c1.date_input("Fecha de Inicio", date.today())
            meses = c2.number_input("Duración (Meses)", 1, 60, 6)
            
            row = u_df[u_df['id']==u_id].iloc[0]
            m1 = c1.text_input("Monto Alquiler", value=str(row['precio_alquiler']))
            m2 = c2.text_input("Monto Contrato", value=str(row['costo_contrato']))
            m3 = st.text_input("Monto Depósito", value=str(row['deposito_base']))
            
            if st.form_submit_button("GRABAR CONTRATO"):
                f_fin = f_ini + timedelta(days=meses*30)
                cid = db_query("INSERT INTO contratos (id_inmueble, id_inquilino, fecha_inicio, fecha_fin, monto_alquiler) VALUES (?,?,?,?,?)", 
                               (u_id, i_id, f_ini, f_fin, cl(m1)), commit=True)
                db_query("INSERT INTO deudas (id_contrato, concepto, monto_debe) VALUES (?, 'Contrato', ?)", (cid, cl(m2)), commit=True)
                db_query("INSERT INTO deudas (id_contrato, concepto, monto_debe) VALUES (?, 'Depósito', ?)", (cid, cl(m3)), commit=True)
                db_query("INSERT INTO deudas (id_contrato, concepto, monto_debe) VALUES (?, 'Mes 1', ?)", (cid, cl(m1)), commit=True)
                st.success("✅ Contrato y Deudas generadas exitosamente."); st.rerun()
    else: st.warning("Cargue Inquilinos y Unidades primero en la sección Maestros.")

# --- SECCIÓN 3: COBRANZAS ---
elif menu == "💰 Cobranzas":
    st.header("Gestión de Cobros")
    deu = db_query("""
        SELECT d.id, inq.nombre, i.tipo, d.concepto, d.monto_debe, d.monto_pago 
        FROM deudas d JOIN contratos c ON d.id_contrato=c.id 
        JOIN inmuebles i ON c.id_inmueble=i.id JOIN inquilinos inq ON c.id_inquilino=inq.id 
        WHERE d.pagado=0
    """)
    if not deu.empty:
        for _, r in deu.iterrows():
            with st.expander(f"💰 {r['nombre']} - {r['tipo']} ({r['concepto']})"):
                cobro = st.text_input("Confirmar Monto", value=str(r['monto_debe']-r['monto_pago']), key=f"c_{r['id']}")
                if st.button("Confirmar Pago", key=f"btn_{r['id']}"):
                    db_query("UPDATE deudas SET monto_pago=?, pagado=1, fecha_pago=? WHERE id=?", (cl(cobro), date.today(), r['id']), commit=True)
                    st.success("Pago registrado."); st.rerun()
    else: st.info("No hay cobros pendientes.")

# --- SECCIÓN 4: MOROSOS ---
elif menu == "🚨 Morosos":
    st.header("Reporte de Morosidad")
    df_m = db_query("""
        SELECT inq.nombre as Inquilino, i.tipo as Unidad, d.concepto, (d.monto_debe-d.monto_pago) as Saldo 
        FROM deudas d JOIN contratos c ON d.id_contrato=c.id 
        JOIN inquilinos inq ON c.id_inquilino=inq.id JOIN inmuebles i ON c.id_inmueble=i.id 
        WHERE d.pagado=0
    """)
    if not df_m.empty: st.table(df_m)
    else: st.success("Todo al día.")

# --- SECCIÓN 5: CAJA Y EXCEL ---
elif menu == "📊 Caja y Excel":
    st.header("Movimientos de Caja y Exportación")
    df_c = db_query("SELECT fecha_pago as Fecha, concepto as Detalle, monto_pago as Importe FROM deudas WHERE pagado=1")
    if not df_c.empty:
        st.metric("Total en Caja", f_m(df_c['Importe'].sum()))
        st.dataframe(df_c, use_container_width=True, hide_index=True)
        # Lógica de Excel
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df_c.to_excel(writer, index=False, sheet_name='Pagos')
        st.download_button("📥 Descargar Reporte Excel", output.getvalue(), "Caja_NL.xlsx")
    else: st.info("Caja vacía.")

# --- SECCIÓN 6: MAESTROS (ABM COMPLETO) ---
elif menu == "⚙️ Maestros":
    st.header("Configuración de Maestros")
    t1, t2, t3, t4 = st.tabs(["👤 Inquilinos", "🏢 Bloques", "🏠 Unidades", "📋 Contratos Activos"])
    
    with t1:
        with st.form("fi", clear_on_submit=True):
            n = st.text_input("Nombre"); d = st.text_input("DNI"); c = st.text_input("WhatsApp")
            if st.form_submit_button("Guardar Inquilino"):
                db_query("INSERT INTO inquilinos (nombre, dni, celular) VALUES (?,?,?)", (n, d, c), commit=True); st.rerun()
        df_inq = db_query("SELECT * FROM inquilinos")
        st.dataframe(df_inq, use_container_width=True, hide_index=True)
        id_i = st.number_input("ID Inquilino a borrar", step=1, key="del_i")
        if st.button("Eliminar Inquilino"):
            db_query(f"DELETE FROM inquilinos WHERE id={id_i}", commit=True); st.rerun()

    with t2:
        nb = st.text_input("Nuevo Bloque")
        if st.button("Guardar Bloque"):
            db_query("INSERT INTO bloques (nombre) VALUES (?)", (nb,), commit=True); st.rerun()
        st.table(db_query("SELECT * FROM bloques"))

    with t3:
        bls = db_query("SELECT * FROM bloques")
        if not bls.empty:
            with st.form("fu", clear_on_submit=True):
                bid = st.selectbox("Bloque", bls['id'].tolist(), format_func=lambda x: bls[bls['id']==x]['nombre'].values[0])
                ut = st.text_input("Nombre Unidad (Ej: Local 1)")
                p1 = st.text_input("Alquiler Sug."); p2 = st.text_input("Contrato Sug."); p3 = st.text_input("Depósito Sug.")
                if st.form_submit_button("Guardar Unidad"):
                    db_query("INSERT INTO inmuebles (id_bloque, tipo, precio_alquiler, costo_contrato, deposito_base) VALUES (?,?,?,?,?)", (bid, ut, cl(p1), cl(p2), cl(p3)), commit=True); st.rerun()
        df_uni = db_query("SELECT i.id, b.nombre as Bloque, i.tipo as Unidad, i.precio_alquiler FROM inmuebles i JOIN bloques b ON i.id_bloque=b.id")
        st.dataframe(df_uni, use_container_width=True, hide_index=True)
        id_u = st.number_input("ID Unidad a borrar", step=1, key="del_u")
        if st.button("Eliminar Unidad"):
            db_query(f"DELETE FROM inmuebles WHERE id={id_u}", commit=True); st.rerun()

    with t4:
        df_con = db_query("""
            SELECT c.id, inq.nombre as Inquilino, i.tipo as Unidad, c.fecha_fin as Vencimiento 
            FROM contratos c JOIN inquilinos inq ON c.id_inquilino=inq.id 
            JOIN inmuebles i ON c.id_inmueble=i.id
        """)
        st.dataframe(df_con, use_container_width=True, hide_index=True)
        id_c = st.number_input("ID Contrato a borrar", step=1, key="del_c")
        if st.button("Eliminar Contrato"):
            db_query(f"DELETE FROM contratos WHERE id={id_c}", commit=True); st.rerun()
