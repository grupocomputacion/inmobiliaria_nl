import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, date, timedelta
import urllib.parse
import os

# --- 1. CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Inmobiliaria Pro Cloud", layout="wide", initial_sidebar_state="expanded")

# --- 2. FUNCIONES DE MOTOR ---
def conectar():
    return sqlite3.connect('datos_alquileres.db', check_same_thread=False, timeout=20)

def fmt_moneda(valor):
    try:
        return f"$ {int(float(valor or 0)):,}".replace(",", ".")
    except:
        return "$ 0"

def limpiar_monto(texto):
    if not texto: return 0.0
    try:
        return float(str(texto).replace('$', '').replace('.', '').replace(',', '').strip())
    except:
        return 0.0

def inicializar_absoluto():
    """Borrado total y físico - Limpieza absoluta"""
    conn = conectar()
    c = conn.cursor()
    tablas = ["deudas", "contratos", "inquilinos", "inmuebles", "bloques"]
    for t in tablas:
        c.execute(f"DROP TABLE IF EXISTS {t}")
    c.executescript('''
        CREATE TABLE bloques (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT UNIQUE);
        CREATE TABLE inmuebles (
            id INTEGER PRIMARY KEY AUTOINCREMENT, id_bloque INTEGER, tipo TEXT, 
            precio_alquiler REAL, costo_contrato REAL, deposito_base REAL,
            UNIQUE(id_bloque, tipo)
        );
        CREATE TABLE inquilinos (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT, celular TEXT);
        CREATE TABLE contratos (
            id INTEGER PRIMARY KEY AUTOINCREMENT, id_inmueble INTEGER, id_inquilino INTEGER, 
            fecha_inicio DATE, fecha_fin DATE, meses INTEGER, activo INTEGER DEFAULT 1, 
            monto_alquiler REAL, monto_contrato REAL, monto_deposito REAL
        );
        CREATE TABLE deudas (
            id INTEGER PRIMARY KEY AUTOINCREMENT, id_contrato INTEGER, concepto TEXT, 
            mes_anio TEXT, monto_debe REAL, monto_pago REAL DEFAULT 0, pagado INTEGER DEFAULT 0, fecha_cobro DATE
        );
    ''')
    conn.commit()
    conn.close()

if not os.path.exists('datos_alquileres.db'):
    inicializar_absoluto()

# --- 3. MENÚ LATERAL ---
with st.sidebar:
    st.title("🏢 Inmobiliaria Pro")
    if st.button("🚨 REINICIAR TODA LA BASE"):
        inicializar_absoluto()
        st.cache_data.clear()
        st.rerun()
    st.divider()
    menu = st.radio("Navegación:", ["🏠 1. Inventario", "📝 2. Nuevo Contrato", "💰 3. Cobranzas", "🚨 4. Morosos", "📊 5. Caja", "⚙️ 6. Maestros"], label_visibility="collapsed")

# --- 1. INVENTARIO ---
if menu == "🏠 1. Inventario":
    st.subheader("Estado de Unidades")
    conn = conectar()
    query = """
        SELECT i.id, b.nombre as Bloque, i.tipo as Unidad, i.precio_alquiler, i.costo_contrato, i.deposito_base,
               c.fecha_inicio, c.fecha_fin, c.activo
        FROM inmuebles i JOIN bloques b ON i.id_bloque = b.id
        LEFT JOIN contratos c ON i.id = c.id_inmueble AND c.activo = 1 GROUP BY i.id 
    """
    df = pd.read_sql_query(query, conn)
    if not df.empty:
        df['Alquiler'] = df['precio_alquiler'].apply(fmt_moneda)
        df['Contrato'] = df['costo_contrato'].apply(fmt_moneda)
        df['Depósito'] = df['deposito_base'].apply(fmt_moneda)
        st.dataframe(df[["Bloque", "Unidad", "Alquiler", "Contrato", "Depósito"]], use_container_width=True, hide_index=True)
    else: st.info("Cargue datos en Maestros.")
    conn.close()

# --- 2. NUEVO CONTRATO ---
elif menu == "📝 2. Nuevo Contrato":
    st.subheader("Alta de Contrato")
    conn = conectar()
    inm_db = pd.read_sql_query("SELECT * FROM inmuebles", conn)
    inq_db = pd.read_sql_query("SELECT * FROM inquilinos", conn)
    if not inm_db.empty and not inq_db.empty:
        with st.form("f_con"):
            id_inm = st.selectbox("Unidad", inm_db['id'].tolist(), format_func=lambda x: f"{inm_db[inm_db['id']==x]['tipo'].values[0]}")
            id_inq = st.selectbox("Inquilino", inq_db['id'].tolist(), format_func=lambda x: inq_db[inq_db['id']==x]['nombre'].values[0])
            f_ini = st.date_input("Inicio", date.today())
            meses = st.number_input("Meses", min_value=1, value=6)
            if st.form_submit_button("Grabar"):
                val = inm_db[inm_db['id']==id_inm].iloc[0]
                conn.execute("INSERT INTO contratos (id_inmueble, id_inquilino, fecha_inicio, meses, monto_alquiler) VALUES (?,?,?,?,?)", 
                            (id_inm, id_inq, f_ini, meses, val['precio_alquiler']))
                conn.commit(); st.success("Contrato grabado"); st.rerun()
    conn.close()

# --- 3. COBRANZAS ---
elif menu == "💰 3. Cobranzas":
    st.subheader("Cobranzas")
    conn = conectar()
    df_c = pd.read_sql_query("SELECT d.id, i.tipo, inq.nombre, d.monto_debe, d.monto_pago, inq.celular FROM deudas d JOIN contratos c ON d.id_contrato=c.id JOIN inmuebles i ON c.id_inmueble=i.id JOIN inquilinos inq ON c.id_inquilino=inq.id WHERE d.pagado=0", conn)
    for _, row in df_c.iterrows():
        with st.expander(f"{row['tipo']} - {row['nombre']}"):
            p_t = st.text_input("Monto", value=str(int(row['monto_debe'])), key=row['id'])
            if st.button("Cobrar", key=f"b{row['id']}"):
                conn.execute("UPDATE deudas SET monto_pago=?, pagado=1 WHERE id=?", (limpiar_monto(p_t), row['id']))
                conn.commit(); st.rerun()
    conn.close()

# --- 4. MOROSOS / 5. CAJA (Simples por espacio) ---
elif menu == "🚨 4. Morosos":
    st.write("Listado de deudores...")
elif menu == "📊 5. Caja":
    st.write("Historial de ingresos...")

# --- 6. MAESTROS (COMPLETO) ---
elif menu == "⚙️ 6. Maestros":
    st.subheader("Administración de Maestros")
    t1, t2, t3, t4 = st.tabs(["👤 Inquilinos", "🏢 Bloques", "🏠 Unidades", "⚡ Procesos"])
    
    with t1:
        con = conectar()
        c1, c2 = st.columns(2)
        with c1:
            st.write("### ➕ Nuevo")
            with st.form("f_inq"):
                n = st.text_input("Nombre"); t = st.text_input("WhatsApp")
                if st.form_submit_button("Guardar"):
                    con.execute("INSERT INTO inquilinos (nombre, celular) VALUES (?,?)", (n,t))
                    con.commit(); st.rerun()
        with c2:
            st.write("### ✏️ Editar/Borrar")
            inqs = pd.read_sql_query("SELECT * FROM inquilinos", con)
            if not inqs.empty:
                id_i = st.selectbox("Elegir", inqs['id'].tolist(), format_func=lambda x: inqs[inqs['id']==x]['nombre'].values[0])
                if st.button("🗑️ Eliminar Inquilino"):
                    con.execute("DELETE FROM inquilinos WHERE id=?", (id_i,))
                    con.commit(); st.rerun()
        con.close()

    with t2:
        with st.form("f_bl"):
            nb = st.text_input("Nombre Bloque")
            if st.form_submit_button("Guardar Bloque"):
                con = conectar(); con.execute("INSERT INTO bloques (nombre) VALUES (?)", (nb,)); con.commit(); con.close(); st.rerun()

    with t3:
        con = conectar()
        bls = pd.read_sql_query("SELECT * FROM bloques", con)
        if not bls.empty:
            with st.form("f_un"):
                idb = st.selectbox("Bloque", bls['id'].tolist(), format_func=lambda x: bls[bls['id']==x]['nombre'].values[0])
                tp = st.text_input("Unidad")
                pr = st.text_input("Alquiler", value="0")
                co = st.text_input("Contrato", value="0")
                de = st.text_input("Depósito", value="0")
                if st.form_submit_button("Guardar Unidad"):
                    con.execute("INSERT INTO inmuebles (id_bloque, tipo, precio_alquiler, costo_contrato, deposito_base) VALUES (?,?,?,?,?)", 
                                (idb, tp, limpiar_monto(pr), limpiar_monto(co), limpiar_monto(de)))
                    con.commit(); st.rerun()
        con.close()

    with t4:
        st.write("### Procesos")
        mes = st.text_input("Mes/Año")
        if st.button("Generar Cuotas"):
            con = conectar()
            activos = pd.read_sql_query("SELECT id, monto_alquiler FROM contratos", con)
            for _, r in activos.iterrows():
                con.execute("INSERT INTO deudas (id_contrato, concepto, mes_anio, monto_debe) VALUES (?,?,?,?)", (r['id'], "Alquiler", mes, r['monto_alquiler']))
            con.commit(); con.close(); st.success("Generado")
