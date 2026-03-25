import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, date, timedelta
import os
import io

# ==========================================
# 1. CONFIGURACIÓN E IDENTIDAD (V.1.0)
# ==========================================
st.set_page_config(page_title="NL Propiedades - V.1.0", layout="wide")

# Estilo Dorado NL
st.markdown("""
    <style>
    .stButton>button { background-color: #D4AF37; color: black; font-weight: bold; width: 100%; border-radius: 5px; }
    h1, h2, h3 { color: #D4AF37; }
    .stBadge { background-color: #D4AF37; color: black; }
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 2. MOTOR DE DATOS (CONEXIÓN SEGURA)
# ==========================================
def conectar():
    conn = sqlite3.connect('datos_alquileres.db', check_same_thread=False)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def inicializar_db():
    conn = conectar()
    cur = conn.cursor()
    cur.executescript('''
        CREATE TABLE IF NOT EXISTS bloques (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT UNIQUE);
        CREATE TABLE IF NOT EXISTS inquilinos (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT, dni TEXT, celular TEXT);
        CREATE TABLE IF NOT EXISTS inmuebles (id INTEGER PRIMARY KEY AUTOINCREMENT, id_bloque INTEGER, tipo TEXT, precio_alquiler INTEGER, costo_contrato INTEGER, deposito_base INTEGER, FOREIGN KEY(id_bloque) REFERENCES bloques(id) ON DELETE CASCADE);
        CREATE TABLE IF NOT EXISTS contratos (id INTEGER PRIMARY KEY AUTOINCREMENT, id_inmueble INTEGER, id_inquilino INTEGER, fecha_inicio DATE, fecha_fin DATE, monto_alquiler INTEGER, activo INTEGER DEFAULT 1, FOREIGN KEY(id_inmueble) REFERENCES inmuebles(id) ON DELETE CASCADE);
        CREATE TABLE IF NOT EXISTS deudas (id INTEGER PRIMARY KEY AUTOINCREMENT, id_contrato INTEGER, concepto TEXT, monto_debe INTEGER, monto_pago INTEGER DEFAULT 0, pagado INTEGER DEFAULT 0, fecha_pago DATE, FOREIGN KEY(id_contrato) REFERENCES contratos(id) ON DELETE CASCADE);
    ''')
    conn.commit()
    conn.close()

inicializar_db()

# Utilidades
def cl(t): return int(str(t).replace('$', '').replace('.', '').replace(',', '').strip() or 0)
def f_m(v): return f"$ {int(v or 0):,}".replace(",", ".")

# ==========================================
# 3. BARRA LATERAL (LOGO Y VERSIÓN)
# ==========================================
with st.sidebar:
    # RECUPERAMOS EL LOGO
    if os.path.exists("alquileres.jpg"):
        st.image("alquileres.jpg", use_container_width=True)
    else:
        st.title("NL PROPIEDADES")
    
    st.write("---")
    st.caption("🚀 **Versión: V.1.0**") # IDENTIFICADOR DE VERSIÓN
    st.write("---")
    
    menu = st.radio("NAVEGACIÓN:", 
                    ["🏠 Inventario", "📝 Nuevo Contrato", "💰 Cobranzas", "🚨 Morosos", "📊 Caja y Excel", "⚙️ Maestros"])
    
    st.write("---")
    if st.button("🚨 FORMATEAR TODO"):
        if os.path.exists('datos_alquileres.db'):
            os.remove('datos_alquileres.db')
            st.rerun()

# ==========================================
# 4. LÓGICA DE SECCIONES (SISTEMA V.1.0)
# ==========================================

conn = conectar()

if menu == "🏠 Inventario":
    st.header("Inventario de Unidades")
    df = pd.read_sql_query("""
        SELECT b.nombre as Bloque, i.tipo as Unidad, i.precio_alquiler as [Alquiler Sug.],
        CASE WHEN c.activo = 1 THEN '🔴 OCUPADO' ELSE '🟢 LIBRE' END as Estado
        FROM inmuebles i 
        JOIN bloques b ON i.id_bloque = b.id
        LEFT JOIN contratos c ON i.id = c.id_inmueble AND c.activo = 1
    """, conn)
    st.dataframe(df, use_container_width=True, hide_index=True)

elif menu == "📝 Nuevo Contrato":
    st.header("Alta de Alquiler")
    u_df = pd.read_sql_query("SELECT i.id, b.nombre || ' - ' || i.tipo as ref, i.precio_alquiler, i.costo_contrato, i.deposito_base FROM inmuebles i JOIN bloques b ON i.id_bloque=b.id", conn)
    i_df = pd.read_sql_query("SELECT id, nombre FROM inquilinos", conn)
    
    if not u_df.empty and not i_df.empty:
        with st.form("f_contrato", clear_on_submit=True):
            c1, c2 = st.columns(2)
            u_id = c1.selectbox("Unidad", u_df['id'].tolist(), format_func=lambda x: u_df[u_df['id']==x]['ref'].values[0])
            i_id = c2.selectbox("Inquilino", i_df['id'].tolist(), format_func=lambda x: i_df[i_df['id']==x]['nombre'].values[0])
            f_ini = c1.date_input("Fecha Inicio", date.today())
            meses = c2.number_input("Meses", 1, 60, 6)
            
            row = u_df[u_df['id']==u_id].iloc[0]
            m1 = c1.text_input("Alquiler Pactado", value=str(row['precio_alquiler']))
            m2 = c2.text_input("Costo Contrato", value=str(row['costo_contrato']))
            m3 = st.text_input("Depósito", value=str(row['deposito_base']))
            
            if st.form_submit_button("GRABAR CONTRATO"):
                f_fin = f_ini + timedelta(days=meses*30)
                cur = conn.cursor()
                cur.execute("INSERT INTO contratos (id_inmueble, id_inquilino, fecha_inicio, fecha_fin, monto_alquiler) VALUES (?,?,?,?,?)", (u_id, i_id, f_ini, f_fin, cl(m1)))
                cid = cur.lastrowid
                cur.executemany("INSERT INTO deudas (id_contrato, concepto, monto_debe) VALUES (?,?,?)", 
                                [(cid, "Costo Contrato", cl(m2)), (cid, "Depósito", cl(m3)), (cid, "Mes 1", cl(m1))])
                conn.commit()
                st.success("✅ Contrato y Deudas generadas correctamente.")
    else: st.warning("Cargue Inquilinos y Unidades primero en Maestros.")

elif menu == "💰 Cobranzas":
    st.header("Gestión de Cobros")
    deu = pd.read_sql_query("SELECT d.id, inq.nombre, i.tipo, d.concepto, d.monto_debe, d.monto_pago FROM deudas d JOIN contratos c ON d.id_contrato=c.id JOIN inmuebles i ON c.id_inmueble=i.id JOIN inquilinos inq ON c.id_inquilino=inq.id WHERE d.pagado=0", conn)
    for _, r in deu.iterrows():
        with st.expander(f"Cobrar a: {r['nombre']} - {r['tipo']} ({r['concepto']})"):
            m_p = st.text_input("Monto", value=str(r['monto_debe']-r['monto_pago']), key=f"c_{r['id']}")
            if st.button("Confirmar Pago", key=f"b_{r['id']}"):
                conn.execute("UPDATE deudas SET monto_pago=?, pagado=1, fecha_pago=? WHERE id=?", (cl(m_p), date.today(), r['id']))
                conn.commit(); st.rerun()

elif menu == "🚨 Morosos":
    st.header("Reporte de Morosidad")
    df_m = pd.read_sql_query("SELECT inq.nombre as Inquilino, i.tipo as Unidad, d.concepto, d.monto_debe as Saldo FROM deudas d JOIN contratos c ON d.id_contrato=c.id JOIN inmuebles i ON c.id_inmueble=i.id JOIN inquilinos inq ON c.id_inquilino=inq.id WHERE d.pagado=0", conn)
    st.table(df_m)

elif menu == "📊 Caja y Excel":
    st.header("Movimientos de Caja")
    df_c = pd.read_sql_query("SELECT fecha_pago as Fecha, concepto as Detalle, monto_pago as Importe FROM deudas WHERE pagado=1", conn)
    if not df_c.empty:
        st.metric("Total Recaudado", f_m(df_c['Importe'].sum()))
        st.dataframe(df_c, use_container_width=True)
        # EXPORTAR A EXCEL
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df_c.to_excel(writer, index=False, sheet_name='Caja')
        st.download_button("📥 Descargar Reporte Excel", output.getvalue(), "Caja_NL.xlsx")
    else: st.info("No hay cobros registrados.")

elif menu == "⚙️ Maestros":
    st.header("Configuración del Sistema")
    t1, t2, t3, t4 = st.tabs(["Inquilinos", "Bloques", "Unidades", "Eliminar Datos"])
    
    with t1:
        with st.form("f_inq"):
            n = st.text_input("Nombre"); d = st.text_input("DNI"); c = st.text_input("WhatsApp")
            if st.form_submit_button("Añadir"):
                conn.execute("INSERT INTO inquilinos (nombre, dni, celular) VALUES (?,?,?)", (n, d, c)); conn.commit(); st.rerun()
        df_i = pd.read_sql_query("SELECT * FROM inquilinos", conn)
        st.dataframe(df_i, use_container_width=True)
        id_i = st.number_input("ID Inquilino a borrar", step=1, value=0)
        if st.button("🗑️ Borrar Inquilino"):
            conn.execute(f"DELETE FROM inquilinos WHERE id={id_i}"); conn.commit(); st.rerun()

    with t2:
        nb = st.text_input("Nombre Bloque")
        if st.button("Guardar Bloque"):
            conn.execute("INSERT INTO bloques (nombre) VALUES (?)", (nb,)); conn.commit(); st.rerun()
        st.table(pd.read_sql_query("SELECT * FROM bloques", conn))

    with t3:
        bls = pd.read_sql_query("SELECT * FROM bloques", conn)
        if not bls.empty:
            with st.form("f_uni"):
                bid = st.selectbox("Bloque", bls['id'].tolist(), format_func=lambda x: bls[bls['id']==x]['nombre'].values[0])
                ut = st.text_input("Unidad")
                p1 = st.text_input("Alquiler Sug."); p2 = st.text_input("Contrato Sug."); p3 = st.text_input("Depósito Sug.")
                if st.form_submit_button("Guardar Unidad"):
                    conn.execute("INSERT INTO inmuebles (id_bloque, tipo, precio_alquiler, costo_contrato, deposito_base) VALUES (?,?,?,?,?)", (bid, ut, cl(p1), cl(p2), cl(p3))); conn.commit(); st.rerun()
        st.dataframe(pd.read_sql_query("SELECT i.id, b.nombre as Bloque, i.tipo as Unidad FROM inmuebles i JOIN bloques b ON i.id_bloque=b.id", conn))

    with t4:
        st.subheader("Eliminar Contratos")
        df_c = pd.read_sql_query("SELECT c.id, inq.nombre as Inquilino, i.tipo as Unidad FROM contratos c JOIN inquilinos inq ON c.id_inquilino=inq.id JOIN inmuebles i ON c.id_inmueble=i.id", conn)
        st.dataframe(df_c, use_container_width=True)
        idc = st.number_input("ID Contrato a borrar", step=1, value=0)
        if st.button("🗑️ ELIMINAR CONTRATO"):
            conn.execute(f"DELETE FROM contratos WHERE id={idc}"); conn.commit(); st.rerun()

conn.close()
