import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, date, timedelta
import os

# 1. CONFIGURACION
st.set_page_config(page_title="NL Propiedades", layout="wide")

# 2. BASE DE DATOS (MIGRACION AUTOMATICA)
def conectar():
    return sqlite3.connect('datos_alquileres.db', check_same_thread=False)

conn = conectar()
cursor = conn.cursor()
cursor.execute("CREATE TABLE IF NOT EXISTS bloques (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT UNIQUE)")
cursor.execute("CREATE TABLE IF NOT EXISTS inmuebles (id INTEGER PRIMARY KEY AUTOINCREMENT, id_bloque INTEGER, tipo TEXT, precio_alquiler INTEGER, costo_contrato INTEGER, deposito_base INTEGER)")
cursor.execute("CREATE TABLE IF NOT EXISTS inquilinos (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT, celular TEXT, dni TEXT, direccion TEXT, emergencia_contacto TEXT, procedencia TEXT, grupo TEXT)")
cursor.execute("CREATE TABLE IF NOT EXISTS contratos (id INTEGER PRIMARY KEY AUTOINCREMENT, id_inmueble INTEGER, id_inquilino INTEGER, fecha_inicio DATE, fecha_fin DATE, meses INTEGER, activo INTEGER DEFAULT 1, monto_alquiler INTEGER, monto_contrato INTEGER, monto_deposito INTEGER)")
cursor.execute("CREATE TABLE IF NOT EXISTS deudas (id INTEGER PRIMARY KEY AUTOINCREMENT, id_contrato INTEGER, concepto TEXT, mes_anio TEXT, monto_debe INTEGER, monto_pago INTEGER DEFAULT 0, pagado INTEGER DEFAULT 0, fecha_cobro DATE)")
conn.commit()

# MIGRACION DE COLUMNAS FALTANTES
tablas_cols = {
    "inquilinos": ["celular", "dni", "direccion", "emergencia_contacto", "procedencia", "grupo"],
    "inmuebles": ["precio_alquiler", "costo_contrato", "deposito_base"]
}
for tabla, cols in tablas_cols.items():
    for col in cols:
        try: cursor.execute(f"ALTER TABLE {tabla} ADD COLUMN {col} TEXT")
        except: pass
conn.commit()

# 3. BARRA LATERAL
with st.sidebar:
    try: st.image("logo.jpg", use_container_width=True)
    except: st.title("NL PROPIEDADES")
    menu = st.radio("MENÚ", ["🏠 1. Inventario", "📝 2. Nuevo Contrato", "💰 3. Cobranzas", "🚨 4. Morosos", "📊 5. Caja", "⚙️ 6. Maestros"])
    if st.button("🚨 RESET TOTAL"):
        os.remove('datos_alquileres.db')
        st.rerun()

# --- FUNCIONES UTILES ---
def fmt(v): return f"$ {int(v or 0):,}".replace(",", ".")
def cl(t): return int(str(t).replace('$', '').replace('.', '').replace(',', '').strip() or 0)

# --- SECCION 1: INVENTARIO ---
if menu == "🏠 1. Inventario":
    st.header("1. Inventario de Unidades")
    df = pd.read_sql_query("""SELECT b.nombre as Bloque, i.tipo as Unidad, i.precio_alquiler, i.costo_contrato, i.deposito_base, MAX(c.fecha_fin) as Vence, MAX(c.activo) as ocupado FROM inmuebles i JOIN bloques b ON i.id_bloque = b.id LEFT JOIN contratos c ON i.id = c.id_inmueble AND c.activo = 1 GROUP BY i.id""", conn)
    if not df.empty:
        df['Estado'] = df['ocupado'].apply(lambda x: "🔴 OCUPADO" if x == 1 else "🟢 LIBRE")
        st.dataframe(df[["Bloque", "Unidad", "Estado", "Vence", "precio_alquiler", "costo_contrato", "deposito_base"]], use_container_width=True)
    else: st.info("Cargue datos en Maestros")

# --- SECCION 2: NUEVO CONTRATO ---
if menu == "📝 2. Nuevo Contrato":
    st.header("2. Nuevo Contrato")
    inm = pd.read_sql_query("SELECT i.id, b.nombre || ' - ' || i.tipo as ref, i.precio_alquiler, i.costo_contrato, i.deposito_base FROM inmuebles i JOIN bloques b ON i.id_bloque=b.id", conn)
    inq = pd.read_sql_query("SELECT id, nombre FROM inquilinos", conn)
    if not inm.empty and not inq.empty:
        with st.form("f2"):
            u_id = st.selectbox("Unidad", inm['id'].tolist(), format_func=lambda x: inm[inm['id']==x]['ref'].values[0])
            i_id = st.selectbox("Inquilino", inq['id'].tolist(), format_func=lambda x: inq[inq['id']==x]['nombre'].values[0])
            f_ini = st.date_input("Inicio", date.today())
            meses = st.number_input("Meses", 1, 60, 6)
            row_u = inm[inm['id']==u_id].iloc[0]
            val_alq = st.text_input("Alquiler", value=str(row_u['precio_alquiler']))
            val_con = st.text_input("Contrato", value=str(row_u['costo_contrato']))
            val_dep = st.text_input("Depósito", value=str(row_u['deposito_base']))
            if st.form_submit_button("GRABAR"):
                f_fin = f_ini + timedelta(days=meses*30)
                cursor.execute("INSERT INTO contratos (id_inmueble, id_inquilino, fecha_inicio, fecha_fin, meses, monto_alquiler, monto_contrato, monto_deposito) VALUES (?,?,?,?,?,?,?,?)", (u_id, i_id, f_ini, f_fin, meses, cl(val_alq), cl(val_con), cl(val_dep)))
                cid = cursor.lastrowid
                m_txt = f_ini.strftime("%m/%Y")
                cursor.executemany("INSERT INTO deudas (id_contrato, concepto, mes_anio, monto_debe) VALUES (?,?,?,?)", [(cid, "Contrato", m_txt, cl(val_con)), (cid, "Depósito", m_txt, cl(val_dep)), (cid, "Mes 1", m_txt, cl(val_alq))])
                conn.commit(); st.success("Grabado"); st.rerun()

# --- SECCION 3: COBRANZAS ---
if menu == "💰 3. Cobranzas":
    st.header("3. Cobranzas")
    deudas = pd.read_sql_query("SELECT d.id, inq.nombre, i.tipo, d.concepto, d.mes_anio, d.monto_debe, d.monto_pago FROM deudas d JOIN contratos c ON d.id_contrato=c.id JOIN inmuebles i ON c.id_inmueble=i.id JOIN inquilinos inq ON c.id_inquilino=inq.id WHERE d.pagado = 0", conn)
    for _, r in deudas.iterrows():
        with st.expander(f"{r['nombre']} - {r['tipo']} ({r['concepto']})"):
            pago = st.text_input("Monto", value=str(int(r['monto_debe']-r['monto_pago'])), key=r['id'])
            if st.button("Cobrar", key=f"b{r['id']}"):
                np = r['monto_pago'] + cl(pago)
                cursor.execute("UPDATE deudas SET monto_pago=?, pagado=?, fecha_cobro=? WHERE id=?", (np, 1 if np>=r['monto_debe'] else 0, date.today(), r['id']))
                conn.commit(); st.rerun()

# --- SECCION 4: MOROSOS ---
if menu == "🚨 4. Morosos":
    st.header("4. Morosos")
    dfm = pd.read_sql_query("SELECT inq.nombre, i.tipo, d.concepto, (d.monto_debe-d.monto_pago) as Saldo FROM deudas d JOIN contratos c ON d.id_contrato=c.id JOIN inmuebles i ON c.id_inmueble=i.id JOIN inquilinos inq ON c.id_inquilino=inq.id WHERE d.pagado=0", conn)
    st.table(dfm)

# --- SECCION 5: CAJA ---
if menu == "📊 5. Caja":
    st.header("5. Caja")
    dfc = pd.read_sql_query("SELECT fecha_cobro, concepto, monto_pago FROM deudas WHERE pagado=1", conn)
    st.dataframe(dfc)

# --- SECCION 6: MAESTROS ---
if menu == "⚙️ 6. Maestros":
    st.header("6. Maestros")
    tab1, tab2, tab3, tab4 = st.tabs(["Inquilinos", "Bloques", "Unidades", "Contratos"])
    with tab1:
        with st.form("f_inq"):
            n = st.text_input("Nombre"); d = st.text_input("DNI"); w = st.text_input("WhatsApp")
            if st.form_submit_button("Guardar"):
                cursor.execute("INSERT INTO inquilinos (nombre, dni, celular) VALUES (?,?,?)", (n, d, w))
                conn.commit(); st.rerun()
        st.write("---")
        # BOTON BORRAR INQUILINO
        inqs = pd.read_sql_query("SELECT * FROM inquilinos", conn)
        if not inqs.empty:
            sel_i = st.selectbox("Borrar Inquilino", inqs['id'].tolist(), format_func=lambda x: inqs[inqs['id']==x]['nombre'].values[0])
            if st.button("Borrar"): cursor.execute(f"DELETE FROM inquilinos WHERE id={sel_i}"); conn.commit(); st.rerun()
    with tab2:
        nb = st.text_input("Nuevo Bloque")
        if st.button("Guardar Bloque"):
            cursor.execute("INSERT INTO bloques (nombre) VALUES (?)", (nb,))
            conn.commit(); st.rerun()
    with tab3:
        bls = pd.read_sql_query("SELECT * FROM bloques", conn)
        if not bls.empty:
            with st.form("f_u"):
                bid = st.selectbox("Bloque", bls['id'].tolist(), format_func=lambda x: bls[bls['id']==x]['nombre'].values[0])
                tp = st.text_input("Unidad")
                p1 = st.text_input("Alquiler"); p2 = st.text_input("Contrato"); p3 = st.text_input("Depósito")
                if st.form_submit_button("Guardar Unidad"):
                    cursor.execute("INSERT INTO inmuebles (id_bloque, tipo, precio_alquiler, costo_contrato, deposito_base) VALUES (?,?,?,?,?)", (bid, tp, cl(p1), cl(p2), cl(p3)))
                    conn.commit(); st.rerun()
    with tab4:
        df_con = pd.read_sql_query("SELECT c.id, inq.nombre, i.tipo, c.activo FROM contratos c JOIN inquilinos inq ON c.id_inquilino=inq.id JOIN inmuebles i ON c.id_inmueble=i.id", conn)
        st.dataframe(df_con)
        if not df_con.empty:
            sel_c = st.selectbox("Borrar Contrato", df_con['id'].tolist())
            if st.button("Eliminar Contrato"):
                cursor.execute(f"DELETE FROM deudas WHERE id_contrato={sel_c}")
                cursor.execute(f"DELETE FROM contratos WHERE id={sel_c}")
                conn.commit(); st.rerun()
