import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, date, timedelta
import os

# ==========================================
# 1. CONFIGURACIÓN E IDENTIDAD VISUAL
# ==========================================
st.set_page_config(page_title="NL Propiedades - Gestión", page_icon="🏠", layout="wide")

st.markdown("""
    <style>
    .stButton>button { background-color: #D4AF37; color: black; border-radius: 5px; font-weight: bold; width: 100%; }
    .stButton>button:hover { background-color: #B8860B; color: white; }
    h1, h2, h3, h4 { color: #D4AF37; }
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 2. MOTOR DE BASE DE DATOS (MIGRACIÓN AUTOMÁTICA)
# ==========================================
def conectar():
    return sqlite3.connect('datos_alquileres.db', check_same_thread=False, timeout=30)

conn = conectar()
cursor = conn.cursor()

# Creación de tablas si no existen
cursor.execute("CREATE TABLE IF NOT EXISTS bloques (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT UNIQUE)")
cursor.execute("CREATE TABLE IF NOT EXISTS inmuebles (id INTEGER PRIMARY KEY AUTOINCREMENT, id_bloque INTEGER, tipo TEXT, precio_alquiler INTEGER, costo_contrato INTEGER, deposito_base INTEGER)")
cursor.execute("CREATE TABLE IF NOT EXISTS inquilinos (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT, celular TEXT, dni TEXT, direccion TEXT, emergencia_contacto TEXT, procedencia TEXT, grupo TEXT)")
cursor.execute("CREATE TABLE IF NOT EXISTS contratos (id INTEGER PRIMARY KEY AUTOINCREMENT, id_inmueble INTEGER, id_inquilino INTEGER, fecha_inicio DATE, fecha_fin DATE, meses INTEGER, activo INTEGER DEFAULT 1, monto_alquiler INTEGER, monto_contrato INTEGER, monto_deposito INTEGER)")
cursor.execute("CREATE TABLE IF NOT EXISTS deudas (id INTEGER PRIMARY KEY AUTOINCREMENT, id_contrato INTEGER, concepto TEXT, mes_anio TEXT, monto_debe INTEGER, monto_pago INTEGER DEFAULT 0, pagado INTEGER DEFAULT 0, fecha_cobro DATE)")
conn.commit()

# MIGRACIÓN: Asegura que las columnas nuevas existan
columnas_inquilinos = ["celular", "dni", "direccion", "emergencia_contacto", "procedencia", "grupo"]
for col in columnas_inquilinos:
    try: cursor.execute(f"ALTER TABLE inquilinos ADD COLUMN {col} TEXT")
    except: pass
conn.commit()

# Utilidades
def fmt_moneda(v): return f"$ {int(v or 0):,}".replace(",", ".")
def limpiar_monto(t): return int(str(t).replace('$', '').replace('.', '').replace(',', '').strip() or 0)

# ==========================================
# 3. BARRA LATERAL (MENÚ)
# ==========================================
with st.sidebar:
    st.title("NL PROPIEDADES")
    st.divider()
    # Selector de Menú
    menu = st.radio("Navegación:", 
                    ["🏠 1. Inventario", 
                     "📝 2. Nuevo Contrato", 
                     "💰 3. Cobranzas", 
                     "🚨 4. Morosos", 
                     "📊 5. Caja", 
                     "⚙️ 6. Maestros"])
    st.divider()
    if st.button("🚨 RESETEAR BASE DE DATOS"):
        if os.path.exists('datos_alquileres.db'): os.remove('datos_alquileres.db')
        st.rerun()

# ==========================================
# 4. LÓGICA DE SECCIONES (BLOQUES INDEPENDIENTES)
# ==========================================

# --- SECCIÓN 1: INVENTARIO ---
if menu == "🏠 1. Inventario":
    st.header("1. Inventario de Unidades")
    query = """
        SELECT b.nombre as Bloque, i.tipo as Unidad, i.precio_alquiler, i.costo_contrato, i.deposito_base,
               MAX(c.fecha_fin) as Vencimiento, MAX(c.activo) as ocupado
        FROM inmuebles i JOIN bloques b ON i.id_bloque = b.id
        LEFT JOIN contratos c ON i.id = c.id_inmueble AND c.activo = 1
        GROUP BY i.id
    """
    df = pd.read_sql_query(query, conn)
    if not df.empty:
        df['Estado'] = df['ocupado'].apply(lambda x: "🔴 OCUPADO" if x == 1 else "🟢 LIBRE")
        st.dataframe(df[["Bloque", "Unidad", "Estado", "Vencimiento", "precio_alquiler", "costo_contrato", "deposito_base"]], use_container_width=True, hide_index=True)
    else: st.info("Cargue datos en la Sección 6: Maestros.")

# --- SECCIÓN 2: NUEVO CONTRATO ---
if menu == "📝 2. Nuevo Contrato":
    st.header("2. Alta de Alquiler")
    unid = pd.read_sql_query("SELECT i.id, b.nombre || ' - ' || i.tipo as ref, i.precio_alquiler, i.costo_contrato, i.deposito_base FROM inmuebles i JOIN bloques b ON i.id_bloque=b.id", conn)
    inqs = pd.read_sql_query("SELECT id, nombre FROM inquilinos", conn)
    if not unid.empty and not inqs.empty:
        with st.form("form_nuevo_contrato"):
            c1, c2 = st.columns(2)
            u_sel = c1.selectbox("Unidad", unid['id'].tolist(), format_func=lambda x: unid[unid['id']==x]['ref'].values[0])
            i_sel = c2.selectbox("Inquilino", inqs['id'].tolist(), format_func=lambda x: inqs[inqs['id']==x]['nombre'].values[0])
            f_ini = c1.date_input("Inicio", datetime.now())
            meses = c2.number_input("Meses", 1, 60, 6)
            row = unid[unid['id']==u_sel].iloc[0]
            m1 = c1.text_input("Alquiler", value=str(row['precio_alquiler']))
            m2 = c2.text_input("Contrato", value=str(row['costo_contrato']))
            m3 = st.text_input("Depósito", value=str(row['deposito_base']))
            if st.form_submit_button("GRABAR CONTRATO"):
                f_fin = f_ini + timedelta(days=meses*30)
                cursor.execute("INSERT INTO contratos (id_inmueble, id_inquilino, fecha_inicio, fecha_fin, meses, monto_alquiler, monto_contrato, monto_deposito) VALUES (?,?,?,?,?,?,?,?)", (u_sel, i_sel, f_ini, f_fin, meses, limpiar_monto(m1), limpiar_monto(m2), limpiar_monto(m3)))
                cid = cursor.lastrowid
                m_txt = f_ini.strftime("%m/%Y")
                cursor.executemany("INSERT INTO deudas (id_contrato, concepto, mes_anio, monto_debe) VALUES (?,?,?,?)", [(cid, "Contrato", m_txt, limpiar_monto(m2)), (cid, "Depósito", m_txt, limpiar_monto(m3)), (cid, "Mes 1", m_txt, limpiar_monto(m1))])
                conn.commit(); st.success("¡Contrato Guardado!"); st.rerun()
    else: st.warning("Primero cargue Inquilinos y Unidades en Maestros.")

# --- SECCIÓN 3: COBRANZAS ---
if menu == "💰 3. Cobranzas":
    st.header("3. Gestión de Cobros")
    deu = pd.read_sql_query("SELECT d.id, inq.nombre, i.tipo, d.concepto, d.mes_anio, d.monto_debe, d.monto_pago FROM deudas d JOIN contratos c ON d.id_contrato=c.id JOIN inmuebles i ON c.id_inmueble=i.id JOIN inquilinos inq ON c.id_inquilino=inq.id WHERE d.pagado=0", conn)
    if not deu.empty:
        for _, r in deu.iterrows():
            with st.expander(f"💰 {r['nombre']} - {r['tipo']} ({r['concepto']})"):
                m_p = st.text_input("Monto a cobrar", value=str(r['monto_debe']-r['monto_pago']), key=f"p_{r['id']}")
                c1, c2 = st.columns(2)
                if c1.button("Cobrar", key=f"b_{r['id']}"):
                    np = r['monto_pago'] + limpiar_monto(m_p)
                    cursor.execute("UPDATE deudas SET monto_pago=?, pagado=?, fecha_cobro=? WHERE id=?", (np, 1 if np>=r['monto_debe'] else 0, datetime.now(), r['id']))
                    conn.commit(); st.rerun()
                if c2.button("Borrar Deuda", key=f"del_{r['id']}"):
                    cursor.execute(f"DELETE FROM deudas WHERE id={r['id']}"); conn.commit(); st.rerun()
    else: st.info("No hay deudas pendientes.")

# --- SECCIÓN 4: MOROSOS ---
if menu == "🚨 4. Morosos":
    st.header("4. Reporte Morosidad")
    dfm = pd.read_sql_query("SELECT inq.nombre as Inquilino, i.tipo as Unidad, d.concepto, d.mes_anio as Mes, (d.monto_debe-d.monto_pago) as Saldo FROM deudas d JOIN contratos c ON d.id_contrato=c.id JOIN inmuebles i ON c.id_inmueble=i.id JOIN inquilinos inq ON c.id_inquilino=inq.id WHERE d.pagado=0", conn)
    if not dfm.empty: st.dataframe(dfm, use_container_width=True, hide_index=True)
    else: st.success("¡Sin deudas!")

# --- SECCIÓN 5: CAJA ---
if menu == "📊 5. Caja":
    st.header("5. Ingresos Realizados")
    dfc = pd.read_sql_query("SELECT fecha_cobro as Fecha, concepto as Detalle, monto_pago as Importe FROM deudas WHERE pagado=1", conn)
    if not dfc.empty:
        st.metric("Total Caja", fmt_moneda(df_c['Importe'].sum()))
        st.dataframe(dfc, use_container_width=True, hide_index=True)
    else: st.info("Caja vacía.")

# --- SECCIÓN 6: MAESTROS ---
if menu == "⚙️ 6. Maestros":
    st.header("6. Maestros")
    t1, t2, t3, t4 = st.tabs(["👤 Inquilinos", "🏢 Bloques", "🏠 Unidades", "📋 Contratos"])
    with t1:
        with st.form("f_inq", clear_on_submit=True):
            n = st.text_input("Nombre"); d = st.text_input("DNI"); w = st.text_input("WhatsApp")
            if st.form_submit_button("Cargar Inquilino"):
                cursor.execute("INSERT INTO inquilinos (nombre, dni, celular) VALUES (?,?,?)", (n, d, w))
                conn.commit(); st.rerun()
        st.dataframe(pd.read_sql_query("SELECT id, nombre, dni, celular FROM inquilinos", conn), use_container_width=True)
    with t2:
        nb = st.text_input("Nuevo Bloque")
        if st.button("Guardar Bloque"):
            cursor.execute("INSERT INTO bloques (nombre) VALUES (?)", (nb,))
            conn.commit(); st.rerun()
        st.table(pd.read_sql_query("SELECT * FROM bloques", conn))
    with t3:
        bls = pd.read_sql_query("SELECT * FROM bloques", conn)
        if not bls.empty:
            with st.form("f_u"):
                bid = st.selectbox("Bloque", bls['id'].tolist(), format_func=lambda x: bls[bls['id']==x]['nombre'].values[0])
                ut = st.text_input("Unidad")
                p1 = st.text_input("Alquiler"); p2 = st.text_input("Contrato"); p3 = st.text_input("Depósito")
                if st.form_submit_button("Guardar Unidad"):
                    cursor.execute("INSERT INTO inmuebles (id_bloque, tipo, precio_alquiler, costo_contrato, deposito_base) VALUES (?,?,?,?,?)", (bid, ut, limpiar_monto(p1), limpiar_monto(p2), limpiar_monto(p3)))
                    conn.commit(); st.rerun()
        st.dataframe(pd.read_sql_query("SELECT i.id, b.nombre as Bloque, i.tipo as Unidad FROM inmuebles i JOIN bloques b ON i.id_bloque=b.id", conn))
    with t4:
        df_c = pd.read_sql_query("SELECT c.id, inq.nombre as Inquilino, i.tipo as Unidad, c.activo FROM contratos c JOIN inquilinos inq ON c.id_inquilino=inq.id JOIN inmuebles i ON c.id_inmueble=i.id", conn)
        st.dataframe(df_c, use_container_width=True)
        sel_c = st.number_input("ID Contrato a borrar", step=1, value=0)
        if st.button("Eliminar Contrato"):
            cursor.execute(f"DELETE FROM deudas WHERE id_contrato={sel_c}")
            cursor.execute(f"DELETE FROM contratos WHERE id={sel_c}"); conn.commit(); st.rerun()

conn.close()
