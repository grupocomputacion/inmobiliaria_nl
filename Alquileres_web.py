import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, date, timedelta
import os

# 1. CONFIGURACIÓN INICIAL
st.set_page_config(page_title="NL PROPIEDADES", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
    <style>
    .stButton>button { background-color: #D4AF37; color: black; font-weight: bold; width: 100%; border-radius: 5px; }
    h1, h2, h3 { color: #D4AF37; }
    .stTabs [data-baseweb="tab-list"] { gap: 8px; }
    .stTabs [data-baseweb="tab"] { background-color: #f0f2f6; border-radius: 5px; padding: 10px; }
    </style>
    """, unsafe_allow_html=True)

# 2. BASE DE DATOS
def conectar():
    return sqlite3.connect('datos_alquileres.db', check_same_thread=False)

conn = conectar()
cur = conn.cursor()
cur.executescript('''
    CREATE TABLE IF NOT EXISTS bloques (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT UNIQUE);
    CREATE TABLE IF NOT EXISTS inmuebles (id INTEGER PRIMARY KEY AUTOINCREMENT, id_bloque INTEGER, tipo TEXT, precio_alquiler INTEGER, costo_contrato INTEGER, deposito_base INTEGER);
    CREATE TABLE IF NOT EXISTS inquilinos (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT, celular TEXT, dni TEXT, procedencia TEXT);
    CREATE TABLE IF NOT EXISTS contratos (id INTEGER PRIMARY KEY AUTOINCREMENT, id_inmueble INTEGER, id_inquilino INTEGER, fecha_inicio DATE, fecha_fin DATE, meses INTEGER, activo INTEGER DEFAULT 1, monto_alquiler INTEGER, monto_contrato INTEGER, monto_deposito INTEGER);
    CREATE TABLE IF NOT EXISTS deudas (id INTEGER PRIMARY KEY AUTOINCREMENT, id_contrato INTEGER, concepto TEXT, mes_anio TEXT, monto_debe INTEGER, monto_pago INTEGER DEFAULT 0, pagado INTEGER DEFAULT 0, fecha_cobro DATE);
''')
conn.commit()

# FUNCIONES AUXILIARES
def f_m(v): return f"$ {int(v or 0):,}".replace(",", ".")
def cl(t): return int(str(t).replace('$', '').replace('.', '').replace(',', '').strip() or 0)

# 3. MENÚ LATERAL
with st.sidebar:
    st.title("NL PROPIEDADES")
    st.divider()
    menu = st.radio("NAVEGACIÓN", ["🏠 1. Inventario", "📝 2. Nuevo Contrato", "💰 3. Cobranzas", "🚨 4. Morosos", "📊 5. Caja", "⚙️ 6. Maestros"])
    st.divider()
    if st.button("🚨 RESET TOTAL (BORRAR DATOS)"):
        conn.close()
        if os.path.exists('datos_alquileres.db'): os.remove('datos_alquileres.db')
        st.rerun()

# ==========================================
# SECCIÓN 1: INVENTARIO
# ==========================================
if menu == "🏠 1. Inventario":
    st.header("Inventario de Unidades")
    try:
        df = pd.read_sql_query("""SELECT b.nombre as Bloque, i.tipo as Unidad, i.precio_alquiler, i.costo_contrato, i.deposito_base, MAX(c.fecha_fin) as Vence, MAX(c.activo) as ocupado FROM inmuebles i JOIN bloques b ON i.id_bloque = b.id LEFT JOIN contratos c ON i.id = c.id_inmueble AND c.activo = 1 GROUP BY i.id""", conn)
        if not df.empty:
            df['Estado'] = df['ocupado'].apply(lambda x: "🔴 OCUPADO" if x == 1 else "🟢 LIBRE")
            st.dataframe(df[["Bloque", "Unidad", "Estado", "Vence", "precio_alquiler", "costo_contrato", "deposito_base"]], use_container_width=True)
        else: st.info("Cargue unidades en la sección 6.")
    except Exception as e: st.error(f"Error en Inventario: {e}")

# ==========================================
# SECCIÓN 2: NUEVO CONTRATO
# ==========================================
if menu == "📝 2. Nuevo Contrato":
    st.header("Alta de Alquiler")
    try:
        inm = pd.read_sql_query("SELECT i.id, b.nombre || ' - ' || i.tipo as ref, i.precio_alquiler, i.costo_contrato, i.deposito_base FROM inmuebles i JOIN bloques b ON i.id_bloque=b.id", conn)
        inq = pd.read_sql_query("SELECT id, nombre FROM inquilinos", conn)
        if not inm.empty and not inq.empty:
            with st.form("f_con"):
                u_id = st.selectbox("Seleccione Unidad", inm['id'].tolist(), format_func=lambda x: inm[inm['id']==x]['ref'].values[0])
                i_id = st.selectbox("Seleccione Inquilino", inq['id'].tolist(), format_func=lambda x: inq[inq['id']==x]['nombre'].values[0])
                f_ini = st.date_input("Fecha Inicio", date.today())
                meses = st.number_input("Meses", 1, 60, 6)
                row = inm[inm['id']==u_id].iloc[0]
                val_alq = st.text_input("Alquiler Mensual", value=str(row['precio_alquiler']))
                val_con = st.text_input("Costo Contrato", value=str(row['costo_contrato']))
                val_dep = st.text_input("Depósito Garantía", value=str(row['deposito_base']))
                if st.form_submit_button("GRABAR CONTRATO"):
                    f_fin = f_ini + timedelta(days=meses*30)
                    cur.execute("INSERT INTO contratos (id_inmueble, id_inquilino, fecha_inicio, fecha_fin, meses, monto_alquiler, monto_contrato, monto_deposito) VALUES (?,?,?,?,?,?,?,?)", (u_id, i_id, f_ini, f_fin, meses, cl(val_alq), cl(val_con), cl(val_dep)))
                    cid = cur.lastrowid
                    m_txt = f_ini.strftime("%m/%Y")
                    cur.executemany("INSERT INTO deudas (id_contrato, concepto, mes_anio, monto_debe) VALUES (?,?,?,?)", [(cid, "Contrato", m_txt, cl(val_con)), (cid, "Depósito", m_txt, cl(val_dep)), (cid, "Mes 1", m_txt, cl(val_alq))])
                    conn.commit(); st.success("¡Contrato grabado con éxito!"); st.rerun()
        else: st.warning("Faltan Inquilinos o Unidades cargadas.")
    except Exception as e: st.error(f"Error en Contratos: {e}")

# ==========================================
# SECCIÓN 3: COBRANZAS
# ==========================================
if menu == "💰 3. Cobranzas":
    st.header("Gestión de Cobros")
    try:
        deudas = pd.read_sql_query("SELECT d.id, inq.nombre, i.tipo, d.concepto, d.mes_anio, d.monto_debe, d.monto_pago FROM deudas d JOIN contratos c ON d.id_contrato=c.id JOIN inmuebles i ON c.id_inmueble=i.id JOIN inquilinos inq ON c.id_inquilino=inq.id WHERE d.pagado = 0", conn)
        if not deudas.empty:
            for _, r in deudas.iterrows():
                with st.expander(f"💰 {r['nombre']} - {r['tipo']} ({r['concepto']})"):
                    pago = st.text_input("Monto a cobrar", value=str(int(r['monto_debe']-r['monto_pago'])), key=f"d_{r['id']}")
                    c1, c2 = st.columns(2)
                    if c1.button("Confirmar Pago", key=f"b_{r['id']}"):
                        np = r['monto_pago'] + cl(pago)
                        cur.execute("UPDATE deudas SET monto_pago=?, pagado=?, fecha_cobro=? WHERE id=?", (np, 1 if np>=r['monto_debe'] else 0, date.today(), r['id']))
                        conn.commit(); st.rerun()
                    if c2.button("Eliminar Cuota", key=f"del_{r['id']}"):
                        cur.execute(f"DELETE FROM deudas WHERE id={r['id']}"); conn.commit(); st.rerun()
        else: st.info("No hay cobros pendientes.")
    except Exception as e: st.error(f"Error en Cobranzas: {e}")

# ==========================================
# SECCIÓN 4: MOROSOS
# ==========================================
if menu == "🚨 4. Morosos":
    st.header("Reporte de Morosidad")
    try:
        dfm = pd.read_sql_query("SELECT inq.nombre as Inquilino, i.tipo as Unidad, d.concepto, (d.monto_debe-d.monto_pago) as Saldo FROM deudas d JOIN contratos c ON d.id_contrato=c.id JOIN inmuebles i ON c.id_inmueble=i.id JOIN inquilinos inq ON c.id_inquilino=inq.id WHERE d.pagado=0", conn)
        if not dfm.empty: st.table(dfm)
        else: st.success("No hay morosos.")
    except Exception as e: st.error(f"Error en Morosos: {e}")

# ==========================================
# SECCIÓN 5: CAJA
# ==========================================
if menu == "📊 5. Caja":
    st.header("Ingresos Realizados")
    try:
        dfc = pd.read_sql_query("SELECT fecha_cobro as Fecha, concepto, monto_pago as Importe FROM deudas WHERE pagado=1", conn)
        if not dfc.empty:
            st.metric("Total Recaudado", f_m(dfc['Importe'].sum()))
            st.dataframe(dfc, use_container_width=True)
        else: st.info("Caja vacía.")
    except Exception as e: st.error(f"Error en Caja: {e}")

# ==========================================
# SECCIÓN 6: MAESTROS
# ==========================================
if menu == "⚙️ 6. Maestros":
    st.header("Administración de Maestros")
    tab1, tab2, tab3, tab4 = st.tabs(["👤 Inquilinos", "🏢 Bloques", "🏠 Unidades", "📋 Contratos"])
    
    with tab1: # INQUILINOS
        c1, c2 = st.columns(2)
        with c1:
            with st.form("fi", clear_on_submit=True):
                n = st.text_input("Nombre"); d = st.text_input("DNI"); w = st.text_input("WhatsApp")
                if st.form_submit_button("Cargar Inquilino"):
                    cur.execute("INSERT INTO inquilinos (nombre, dni, celular) VALUES (?,?,?)", (n, d, w))
                    conn.commit(); st.rerun()
        with c2:
            st.write("Inquilinos Cargados")
            dfi = pd.read_sql_query("SELECT id, nombre, dni FROM inquilinos", conn)
            st.dataframe(dfi, use_container_width=True, hide_index=True)
            sel_id = st.number_input("ID a borrar", step=1, value=0)
            if st.button("🗑️ Borrar Inquilino"):
                cur.execute(f"DELETE FROM inquilinos WHERE id={sel_id}"); conn.commit(); st.rerun()

    with tab2: # BLOQUES
        c1, c2 = st.columns(2)
        with c1:
            nb = st.text_input("Nombre del Bloque")
            if st.button("Guardar Bloque"):
                cur.execute("INSERT INTO bloques (nombre) VALUES (?)", (nb,))
                conn.commit(); st.rerun()
        with c2:
            st.table(pd.read_sql_query("SELECT * FROM bloques", conn))

    with tab3: # UNIDADES
        bls = pd.read_sql_query("SELECT * FROM bloques", conn)
        if not bls.empty:
            with st.form("fu"):
                bid = st.selectbox("Bloque", bls['id'].tolist(), format_func=lambda x: bls[bls['id']==x]['nombre'].values[0])
                ut = st.text_input("Nombre Unidad")
                p1 = st.text_input("Alquiler Sugerido"); p2 = st.text_input("Contrato Sugerido"); p3 = st.text_input("Depósito Sugerido")
                if st.form_submit_button("Guardar Unidad"):
                    cur.execute("INSERT INTO inmuebles (id_bloque, tipo, precio_alquiler, costo_contrato, deposito_base) VALUES (?,?,?,?,?)", (bid, ut, cl(p1), cl(p2), cl(p3)))
                    conn.commit(); st.rerun()
        st.dataframe(pd.read_sql_query("SELECT i.id, b.nombre as Bloque, i.tipo as Unidad FROM inmuebles i JOIN bloques b ON i.id_bloque=b.id", conn), use_container_width=True)

    with tab4: # CONTRATOS
        st.write("Historial de Contratos")
        df_c = pd.read_sql_query("SELECT c.id, inq.nombre as Inquilino, i.tipo as Unidad, c.activo FROM contratos c JOIN inquilinos inq ON c.id_inquilino=inq.id JOIN inmuebles i ON c.id_inmueble=i.id", conn)
        st.dataframe(df_c, use_container_width=True, hide_index=True)
        idc = st.number_input("ID Contrato a borrar", step=1, value=0)
        if st.button("Eliminar Contrato"):
            cur.execute(f"DELETE FROM deudas WHERE id_contrato={idc}")
            cur.execute(f"DELETE FROM contratos WHERE id={idc}")
            conn.commit(); st.rerun()

conn.close()
