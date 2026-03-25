import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, date, timedelta
import os

# 1. CONFIGURACION
st.set_page_config(page_title="NL PROPIEDADES", layout="wide")

# 2. CONEXION DIRECTA (SIN FUNCIONES)
conn = sqlite3.connect('datos_alquileres.db', check_same_thread=False)
cursor = conn.cursor()

# CREAR TABLAS (ASEGURAMOS QUE EXISTAN TODOS LOS CAMPOS)
cursor.execute("CREATE TABLE IF NOT EXISTS bloques (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT UNIQUE)")
cursor.execute("CREATE TABLE IF NOT EXISTS inmuebles (id INTEGER PRIMARY KEY AUTOINCREMENT, id_bloque INTEGER, tipo TEXT, precio_alquiler INTEGER, costo_contrato INTEGER, deposito_base INTEGER)")
cursor.execute("CREATE TABLE IF NOT EXISTS inquilinos (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT, dni TEXT, celular TEXT)")
cursor.execute("CREATE TABLE IF NOT EXISTS contratos (id INTEGER PRIMARY KEY AUTOINCREMENT, id_inmueble INTEGER, id_inquilino INTEGER, fecha_inicio DATE, fecha_fin DATE, meses INTEGER, activo INTEGER DEFAULT 1, monto_alquiler INTEGER, monto_contrato INTEGER, monto_deposito INTEGER)")
cursor.execute("CREATE TABLE IF NOT EXISTS deudas (id INTEGER PRIMARY KEY AUTOINCREMENT, id_contrato INTEGER, concepto TEXT, mes_anio TEXT, monto_debe INTEGER, monto_pago INTEGER DEFAULT 0, pagado INTEGER DEFAULT 0, fecha_cobro DATE)")
conn.commit()

# 3. BARRA LATERAL (MENU SIMPLE)
with st.sidebar:
    st.title("NL PROPIEDADES")
    st.write("---")
    # Menu sin emojis ni numeros complejos para evitar errores de string
    menu = st.radio("MENU", ["Inventario", "Nuevo Contrato", "Cobranzas", "Morosos", "Caja", "Maestros"])
    st.write("---")
    if st.button("RESETEAR SISTEMA"):
        if os.path.exists('datos_alquileres.db'):
            conn.close()
            os.remove('datos_alquileres.db')
            st.rerun()

# --- UTILIDADES ---
def cl(t): return int(str(t).replace('$', '').replace('.', '').replace(',', '').strip() or 0)

# ==========================================
# SECCION 1: INVENTARIO
# ==========================================
if menu == "Inventario":
    st.header("1. Inventario")
    # Query simple para que no falle
    df = pd.read_sql_query("SELECT b.nombre as Bloque, i.tipo as Unidad, i.precio_alquiler as Alquiler FROM inmuebles i JOIN bloques b ON i.id_bloque = b.id", conn)
    st.dataframe(df, use_container_width=True)

# ==========================================
# SECCION 2: NUEVO CONTRATO
# ==========================================
if menu == "Nuevo Contrato":
    st.header("2. Nuevo Contrato")
    unidades = pd.read_sql_query("SELECT i.id, b.nombre || ' - ' || i.tipo as ref, i.precio_alquiler, i.costo_contrato, i.deposito_base FROM inmuebles i JOIN bloques b ON i.id_bloque=b.id", conn)
    inquilinos = pd.read_sql_query("SELECT id, nombre FROM inquilinos", conn)
    
    if not unidades.empty and not inquilinos.empty:
        with st.form("form_alta"):
            u_id = st.selectbox("Unidad", unidades['id'].tolist(), format_func=lambda x: unidades[unidades['id']==x]['ref'].values[0])
            i_id = st.selectbox("Inquilino", inquilinos['id'].tolist(), format_func=lambda x: inquilinos[inquilinos['id']==x]['nombre'].values[0])
            f_ini = st.date_input("Fecha Inicio", date.today())
            meses = st.number_input("Meses", 1, 60, 6)
            
            row = unidades[unidades['id']==u_id].iloc[0]
            m1 = st.text_input("Alquiler", value=str(row['precio_alquiler']))
            m2 = st.text_input("Contrato", value=str(row['costo_contrato']))
            m3 = st.text_input("Deposito", value=str(row['deposito_base']))
            
            if st.form_submit_button("GRABAR"):
                f_fin = f_ini + timedelta(days=meses*30)
                cursor.execute("INSERT INTO contratos (id_inmueble, id_inquilino, fecha_inicio, fecha_fin, meses, monto_alquiler, monto_contrato, monto_deposito) VALUES (?,?,?,?,?,?,?,?)", (u_id, i_id, f_ini, f_fin, meses, cl(m1), cl(m2), cl(m3)))
                cid = cursor.lastrowid
                m_txt = f_ini.strftime("%m/%y")
                # Insertamos las 3 deudas iniciales
                cursor.execute("INSERT INTO deudas (id_contrato, concepto, mes_anio, monto_debe) VALUES (?, 'Contrato', ?, ?)", (cid, m_txt, cl(m2)))
                cursor.execute("INSERT INTO deudas (id_contrato, concepto, mes_anio, monto_debe) VALUES (?, 'Deposito', ?, ?)", (cid, m_txt, cl(m3)))
                cursor.execute("INSERT INTO deudas (id_contrato, concepto, mes_anio, monto_debe) VALUES (?, 'Mes 1', ?, ?)", (cid, m_txt, cl(m1)))
                conn.commit()
                st.success("GRABADO CORRECTAMENTE")
    else:
        st.warning("Cargue datos en MAESTROS primero.")

# ==========================================
# SECCION 3: COBRANZAS
# ==========================================
if menu == "Cobranzas":
    st.header("3. Cobranzas")
    deu = pd.read_sql_query("SELECT d.id, inq.nombre, i.tipo, d.concepto, d.monto_debe, d.monto_pago FROM deudas d JOIN contratos c ON d.id_contrato=c.id JOIN inmuebles i ON c.id_inmueble=i.id JOIN inquilinos inq ON c.id_inquilino=inq.id WHERE d.pagado=0", conn)
    for _, r in deu.iterrows():
        with st.expander(f"{r['nombre']} - {r['tipo']} ({r['concepto']})"):
            m_a_cobrar = st.text_input("Monto", value=str(r['monto_debe']-r['monto_pago']), key=f"c_{r['id']}")
            if st.button("Cobrar", key=f"b_{r['id']}"):
                cursor.execute("UPDATE deudas SET monto_pago=?, pagado=1, fecha_cobro=? WHERE id=?", (cl(m_a_cobrar), date.today(), r['id']))
                conn.commit()
                st.rerun()

# ==========================================
# SECCION 4: MOROSOS
# ==========================================
if menu == "Morosos":
    st.header("4. Morosos")
    df_m = pd.read_sql_query("SELECT inq.nombre as Inquilino, i.tipo as Unidad, d.concepto, (d.monto_debe-d.monto_pago) as Saldo FROM deudas d JOIN contratos c ON d.id_contrato=c.id JOIN inmuebles i ON c.id_inmueble=i.id JOIN inquilinos inq ON c.id_inquilino=inq.id WHERE d.pagado=0", conn)
    st.table(df_m)

# ==========================================
# SECCION 5: CAJA
# ==========================================
if menu == "Caja":
    st.header("5. Caja")
    df_c = pd.read_sql_query("SELECT fecha_cobro, concepto, monto_pago FROM deudas WHERE pagado=1", conn)
    st.dataframe(df_c, use_container_width=True)

# ==========================================
# SECCION 6: MAESTROS
# ==========================================
if menu == "Maestros":
    st.header("6. Maestros")
    t1, t2, t3 = st.tabs(["Inquilinos", "Bloques", "Unidades"])
    with t1:
        n = st.text_input("Nombre"); d = st.text_input("DNI")
        if st.button("Cargar Inquilino"):
            cursor.execute("INSERT INTO inquilinos (nombre, dni) VALUES (?,?)", (n, d))
            conn.commit(); st.rerun()
        st.dataframe(pd.read_sql_query("SELECT * FROM inquilinos", conn))
    with t2:
        nb = st.text_input("Nombre Bloque")
        if st.button("Guardar Bloque"):
            cursor.execute("INSERT INTO bloques (nombre) VALUES (?)", (nb,))
            conn.commit(); st.rerun()
    with t3:
        bls = pd.read_sql_query("SELECT * FROM bloques", conn)
        if not bls.empty:
            bid = st.selectbox("Bloque", bls['id'].tolist(), format_func=lambda x: bls[bls['id']==x]['nombre'].values[0])
            ut = st.text_input("Unidad")
            p1 = st.text_input("Alquiler"); p2 = st.text_input("Contrato"); p3 = st.text_input("Deposito")
            if st.button("Guardar Unidad"):
                cursor.execute("INSERT INTO inmuebles (id_bloque, tipo, precio_alquiler, costo_contrato, deposito_base) VALUES (?,?,?,?,?)", (bid, ut, cl(p1), cl(p2), cl(p3)))
                conn.commit(); st.rerun()
