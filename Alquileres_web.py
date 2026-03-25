import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, date, timedelta
import os

# 1. ELIMINAR ESTADOS PREVIOS
st.cache_data.clear()

# 2. CONFIGURACION BASICA
st.set_page_config(page_title="SISTEMA NL", layout="wide")

# 3. BASE DE DATOS (CONEXION DIRECTA)
conn = sqlite3.connect('datos_alquileres.db', check_same_thread=False)
cur = conn.cursor()

# CREAR TABLAS
cur.executescript('''
    CREATE TABLE IF NOT EXISTS bloques (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT UNIQUE);
    CREATE TABLE IF NOT EXISTS inmuebles (id INTEGER PRIMARY KEY AUTOINCREMENT, id_bloque INTEGER, tipo TEXT, precio_alquiler INTEGER, costo_contrato INTEGER, deposito_base INTEGER);
    CREATE TABLE IF NOT EXISTS inquilinos (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT, celular TEXT, dni TEXT);
    CREATE TABLE IF NOT EXISTS contratos (id INTEGER PRIMARY KEY AUTOINCREMENT, id_inmueble INTEGER, id_inquilino INTEGER, fecha_inicio DATE, fecha_fin DATE, meses INTEGER, activo INTEGER DEFAULT 1, monto_alquiler INTEGER, monto_contrato INTEGER, monto_deposito INTEGER);
    CREATE TABLE IF NOT EXISTS deudas (id INTEGER PRIMARY KEY AUTOINCREMENT, id_contrato INTEGER, concepto TEXT, mes_anio TEXT, monto_debe INTEGER, monto_pago INTEGER DEFAULT 0, pagado INTEGER DEFAULT 0, fecha_cobro DATE);
''')
conn.commit()

# 4. MENU LATERAL (TEXTO PLANO PARA EVITAR ERRORES)
with st.sidebar:
    st.title("NL PROPIEDADES")
    st.write("---")
    menu = st.radio("SELECCIONE:", ["INVENTARIO", "CONTRATOS", "COBRANZAS", "MOROSOS", "CAJA", "MAESTROS"])
    st.write("---")
    if st.button("RESETEAR SISTEMA"):
        if os.path.exists('datos_alquileres.db'):
            conn.close()
            os.remove('datos_alquileres.db')
            st.rerun()

# --- UTILIDADES ---
def to_int(v): return int(str(v).replace('$', '').replace('.', '').replace(',', '').strip() or 0)

# ==========================================
# SECCION 1: INVENTARIO
# ==========================================
if menu == "INVENTARIO":
    st.header("1. Inventario")
    df = pd.read_sql_query("SELECT b.nombre as Bloque, i.tipo as Unidad, i.precio_alquiler as Alquiler FROM inmuebles i JOIN bloques b ON i.id_bloque = b.id", conn)
    if not df.empty:
        st.dataframe(df, use_container_width=True)
    else:
        st.info("No hay unidades. Cargue datos en MAESTROS.")

# ==========================================
# SECCION 2: CONTRATOS (ALTA)
# ==========================================
if menu == "CONTRATOS":
    st.header("2. Nuevo Contrato")
    u_df = pd.read_sql_query("SELECT i.id, b.nombre || ' - ' || i.tipo as ref, i.precio_alquiler, i.costo_contrato, i.deposito_base FROM inmuebles i JOIN bloques b ON i.id_bloque=b.id", conn)
    i_df = pd.read_sql_query("SELECT id, nombre FROM inquilinos", conn)
    
    if not u_df.empty and not i_df.empty:
        with st.form("form_alta"):
            sel_u = st.selectbox("Unidad", u_df['id'].tolist(), format_func=lambda x: u_df[u_df['id']==x]['ref'].values[0])
            sel_i = st.selectbox("Inquilino", i_df['id'].tolist(), format_func=lambda x: i_df[i_df['id']==x]['nombre'].values[0])
            f_ini = st.date_input("Fecha Inicio", date.today())
            meses = st.number_input("Meses", 1, 60, 6)
            
            row = u_df[u_df['id']==sel_u].iloc[0]
            m1 = st.text_input("Alquiler", value=str(row['precio_alquiler']))
            m2 = st.text_input("Contrato", value=str(row['costo_contrato']))
            m3 = st.text_input("Deposito", value=str(row['deposito_base']))
            
            if st.form_submit_button("GRABAR"):
                cur.execute("INSERT INTO contratos (id_inmueble, id_inquilino, fecha_inicio, fecha_fin, meses, monto_alquiler, monto_contrato, monto_deposito) VALUES (?,?,?,?,?,?,?,?)", (sel_u, sel_i, f_ini, f_ini + timedelta(days=meses*30), meses, to_int(m1), to_int(m2), to_int(m3)))
                cid = cur.lastrowid
                # DEUDAS
                cur.executemany("INSERT INTO deudas (id_contrato, concepto, mes_anio, monto_debe) VALUES (?,?,?,?)", [
                    (cid, "Contrato", f_ini.strftime("%m/%y"), to_int(m2)),
                    (cid, "Deposito", f_ini.strftime("%m/%y"), to_int(m3)),
                    (cid, "Alquiler 1", f_ini.strftime("%m/%y"), to_int(m1))
                ])
                conn.commit()
                st.success("GRABADO")
    else:
        st.warning("Debe cargar Inquilinos y Unidades en MAESTROS.")

# ==========================================
# SECCION 3: COBRANZAS
# ==========================================
if menu == "COBRANZAS":
    st.header("3. Cobranzas")
    deu = pd.read_sql_query("SELECT d.id, inq.nombre, i.tipo, d.concepto, d.monto_debe, d.monto_pago FROM deudas d JOIN contratos c ON d.id_contrato=c.id JOIN inmuebles i ON c.id_inmueble=i.id JOIN inquilinos inq ON c.id_inquilino=inq.id WHERE d.pagado=0", conn)
    for _, r in deu.iterrows():
        with st.expander(f"{r['nombre']} - {r['tipo']} ({r['concepto']})"):
            m_cobro = st.text_input("Monto", value=str(r['monto_debe']-r['monto_pago']), key=f"c_{r['id']}")
            if st.button("Cobrar", key=f"b_{r['id']}"):
                cur.execute("UPDATE deudas SET monto_pago=?, pagado=?, fecha_cobro=? WHERE id=?", (r['monto_pago']+to_int(m_cobro), 1, date.today(), r['id']))
                conn.commit()
                st.rerun()

# ==========================================
# SECCION 4: MOROSOS
# ==========================================
if menu == "MOROSOS":
    st.header("4. Morosos")
    df_m = pd.read_sql_query("SELECT inq.nombre, i.tipo, d.concepto, (d.monto_debe-d.monto_pago) as Saldo FROM deudas d JOIN contratos c ON d.id_contrato=c.id JOIN inmuebles i ON c.id_inmueble=i.id JOIN inquilinos inq ON c.id_inquilino=inq.id WHERE d.pagado=0", conn)
    st.table(df_m)

# ==========================================
# SECCION 5: CAJA
# ==========================================
if menu == "CAJA":
    st.header("5. Caja")
    df_c = pd.read_sql_query("SELECT fecha_cobro, concepto, monto_pago FROM deudas WHERE pagado=1", conn)
    st.dataframe(df_c, use_container_width=True)

# ==========================================
# SECCION 6: MAESTROS
# ==========================================
if menu == "MAESTROS":
    st.header("6. Maestros")
    t1, t2, t3 = st.tabs(["Inquilinos", "Bloques", "Unidades"])
    with t1:
        with st.form("f1"):
            n = st.text_input("Nombre"); d = st.text_input("DNI")
            if st.form_submit_button("Cargar"):
                cur.execute("INSERT INTO inquilinos (nombre, dni) VALUES (?,?)", (n, d))
                conn.commit(); st.rerun()
        st.dataframe(pd.read_sql_query("SELECT * FROM inquilinos", conn))
    with t2:
        nb = st.text_input("Nuevo Bloque")
        if st.button("Guardar Bloque"):
            cur.execute("INSERT INTO bloques (nombre) VALUES (?)", (nb,))
            conn.commit(); st.rerun()
    with t3:
        bls = pd.read_sql_query("SELECT * FROM bloques", conn)
        if not bls.empty:
            with st.form("f3"):
                bid = st.selectbox("Bloque", bls['id'].tolist(), format_func=lambda x: bls[bls['id']==x]['nombre'].values[0])
                ut = st.text_input("Unidad")
                p1 = st.text_input("Alquiler Sugerido"); p2 = st.text_input("Contrato Sugerido"); p3 = st.text_input("Deposito Sugerido")
                if st.form_submit_button("Guardar Unidad"):
                    cur.execute("INSERT INTO inmuebles (id_bloque, tipo, precio_alquiler, costo_contrato, deposito_base) VALUES (?,?,?,?,?)", (bid, ut, to_int(p1), to_int(p2), to_int(p3)))
                    conn.commit(); st.rerun()
