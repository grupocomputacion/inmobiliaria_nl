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
    return sqlite3.connect('datos_alquileres.db', check_same_thread=False, timeout=10)

def fmt_moneda(valor):
    """Visualización: $ 1.250.000"""
    try:
        return f"$ {int(float(valor or 0)):,}".replace(",", ".")
    except:
        return "$ 0"

def limpiar_monto(texto):
    """Limpia puntos y convierte a número para la DB"""
    if not texto: return 0.0
    try:
        return float(str(texto).replace('$', '').replace('.', '').replace(',', '').strip())
    except:
        return 0.0

def crear_link_whatsapp(tel, mensaje):
    tel_limpio = "".join(filter(str.isdigit, str(tel)))
    texto = urllib.parse.quote(mensaje)
    return f"https://wa.me/{tel_limpio}?text={texto}"

def inicializar_absoluto():
    if os.path.exists('datos_alquileres.db'):
        os.remove('datos_alquileres.db')
    conn = conectar()
    c = conn.cursor()
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

# Asegurar DB
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
    menu = st.radio(
        "Navegación:",
        ["🏠 1. Inventario", "📝 2. Nuevo Contrato", "💰 3. Cobranzas", "🚨 4. Morosos", "📊 5. Caja", "⚙️ 6. Maestros"],
        label_visibility="collapsed"
    )

# ---------------------------------------------------------
# 1. INVENTARIO
# ---------------------------------------------------------
if menu == "🏠 1. Inventario":
    st.subheader("Estado de Unidades y Disponibilidad")
    conn = conectar()
    hoy = date.today()
    query = """
        SELECT i.id, b.nombre as Bloque, i.tipo as Unidad, 
               i.precio_alquiler, i.costo_contrato, i.deposito_base,
               c.fecha_inicio, c.fecha_fin, c.activo
        FROM inmuebles i
        JOIN bloques b ON i.id_bloque = b.id
        LEFT JOIN contratos c ON i.id = c.id_inmueble AND c.activo = 1
        GROUP BY i.id 
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    if not df.empty:
        def calc_sit(row):
            if pd.isna(row['fecha_inicio']) or row['activo'] == 0: return "Libre", "LIBRE HOY"
            f_fin = pd.to_datetime(row['fecha_fin']).date()
            return ("OCUPADO", f_fin.strftime('%d/%m/%Y')) if hoy <= f_fin else ("VENCIDO", "LIBRE HOY")
        
        df[['Situación', 'Disponible Desde']] = df.apply(lambda x: pd.Series(calc_sit(x)), axis=1)
        df['Alquiler'] = df['precio_alquiler'].apply(fmt_moneda)
        df['Contrato'] = df['costo_contrato'].apply(fmt_moneda)
        df['Depósito'] = df['deposito_base'].apply(fmt_moneda)
        
        def color_sit(val):
            color = '#28a745' if val == "Libre" else '#dc3545' if val == "OCUPADO" else '#fd7e14'
            return f'color: {color}; font-weight: bold'

        st.dataframe(df[["Bloque", "Unidad", "Situación", "Disponible Desde", "Alquiler", "Contrato", "Depósito"]].style.applymap(color_sit, subset=['Situación']), 
                     use_container_width=True, hide_index=True)
    else: st.info("Cargue datos en Maestros.")

# ---------------------------------------------------------
# 2. NUEVO CONTRATO
# ---------------------------------------------------------
elif menu == "📝 2. Nuevo Contrato":
    st.subheader("Alta de Contrato")
    conn = conectar()
    inm_db = pd.read_sql_query("SELECT id, tipo, precio_alquiler, costo_contrato, deposito_base FROM inmuebles", conn)
    inq_db = pd.read_sql_query("SELECT id, nombre FROM inquilinos", conn)
    conn.close()
    
    if not inm_db.empty and not inq_db.empty:
        with st.form("f_con"):
            c1, c2 = st.columns(2)
            id_inm = c1.selectbox("Unidad", inm_db['id'].tolist(), format_func=lambda x: f"{inm_db[inm_db['id']==x]['tipo'].values[0]}")
            id_inq = c2.selectbox("Inquilino", inq_db['id'].tolist(), format_func=lambda x: inq_db[inq_db['id']==x]['nombre'].values[0])
            f_ini = c1.date_input("Inicio", date.today())
            meses = c2.number_input("Meses", min_value=1, value=6)
            f_fin = f_ini + timedelta(days=meses * 30)
            
            val_ref = inm_db[inm_db['id'] == id_inm].iloc[0]
            m_alq_t = c1.text_input("Monto Alquiler", value=str(int(val_ref['precio_alquiler'])))
            m_con_t = c2.text_input("Costo Contrato", value=str(int(val_ref['costo_contrato'])))
            m_dep_t = c1.text_input("Depósito", value=str(int(val_ref['deposito_base'])))

            if st.form_submit_button("Grabar Contrato"):
                con = conectar()
                try:
                    cur = con.cursor()
                    cur.execute("INSERT INTO contratos (id_inmueble, id_inquilino, fecha_inicio, fecha_fin, meses, activo, monto_alquiler, monto_contrato, monto_deposito) VALUES (?,?,?,?,?,1,?,?,?)", 
                                (id_inm, id_inq, f_ini, f_fin, meses, limpiar_monto(m_alq_t), limpiar_monto(m_con_t), limpiar_monto(m_dep_t)))
                    con.commit()
                    st.success("Contrato grabado")
                    st.rerun()
                finally:
                    con.close()
    else: st.warning("Cargue datos en Maestros primero.")

# ---------------------------------------------------------
# 3. COBRANZAS
# ---------------------------------------------------------
elif menu == "💰 3. Cobranzas":
    st.subheader("Cobros")
    conn = conectar()
    df_c = pd.read_sql_query("SELECT d.id, i.tipo, inq.nombre, d.monto_debe, d.monto_pago, inq.celular, d.concepto FROM deudas d JOIN contratos c ON d.id_contrato=c.id JOIN inmuebles i ON c.id_inmueble=i.id JOIN inquilinos inq ON c.id_inquilino=inq.id WHERE d.pagado = 0", conn)
    conn.close()
    
    for _, row in df_c.iterrows():
        with st.expander(f"{row['tipo']} - {row['nombre']}"):
            saldo = row['monto_debe'] - row['monto_pago']
            st.write(f"Debe: {fmt_moneda(saldo)}")
            pago_t = st.text_input("Cobrar", value=str(int(saldo)), key=f"c_{row['id']}")
            if st.button("Confirmar", key=f"b_{row['id']}"):
                con = conectar()
                try:
                    nuevo = row['monto_pago'] + limpiar_monto(pago_t)
                    pagado = 1 if nuevo >= row['monto_debe'] else 0
                    con.execute("UPDATE deudas SET monto_pago=?, pagado=?, fecha_cobro=? WHERE id=?", (nuevo, pagado, date.today(), row['id']))
                    con.commit()
                    st.rerun()
                finally:
                    con.close()

# ---------------------------------------------------------
# 4. MOROSOS
# ---------------------------------------------------------
elif menu == "🚨 4. Morosos":
    st.subheader("Deudores")
    conn = conectar()
    df_m = pd.read_sql_query("SELECT inq.nombre as Inquilino, i.tipo as Unidad, (d.monto_debe - d.monto_pago) as Saldo FROM deudas d JOIN contratos c ON d.id_contrato=c.id JOIN inmuebles i ON c.id_inmueble=i.id JOIN inquilinos inq ON c.id_inquilino=inq.id WHERE d.pagado = 0", conn)
    conn.close()
    if not df_m.empty:
        st.error(f"Total Mora: {fmt_moneda(df_m['Saldo'].sum())}")
        df_m['Saldo'] = df_m['Saldo'].apply(fmt_moneda); st.table(df_m)
    else: st.success("Sin deudas.")

# ---------------------------------------------------------
# 5. CAJA
# ---------------------------------------------------------
elif menu == "📊 5. Caja":
    st.subheader("Ingresos")
    conn = conectar()
    df_cj = pd.read_sql_query("SELECT fecha_cobro as Fecha, concepto as Detalle, monto_pago as Monto FROM deudas WHERE pagado=1", conn)
    conn.close()
    if not df_cj.empty:
        st.metric("Total", fmt_moneda(df_cj['Monto'].sum()))
        df_cj['Monto'] = df_cj['Monto'].apply(fmt_moneda); st.table(df_cj)

# ---------------------------------------------------------
# 6. MAESTROS
# ---------------------------------------------------------
elif menu == "⚙️ 6. Maestros":
    st.subheader("Administración de Maestros")
    t1, t2, t3, t4 = st.tabs(["👤 Inquilinos", "🏢 Bloques", "🏠 Unidades", "⚡ Procesos"])
    
    with t3:
        con = conectar()
        bls = pd.read_sql_query("SELECT * FROM bloques", con)
        col_a, col_b = st.columns(2)
        
        with col_a:
            st.write("### ➕ Nueva Unidad")
            if not bls.empty:
                with st.form("f_alta"):
                    idb = st.selectbox("Bloque", bls['id'].tolist(), format_func=lambda x: bls[bls['id']==x]['nombre'].values[0])
                    tp = st.text_input("Nombre Unidad")
                    pr_t = st.text_input("Alquiler", value="0")
                    co_t = st.text_input("Contrato", value="0")
                    de_t = st.text_input("Depósito", value="0")
                    if st.form_submit_button("Guardar"):
                        try:
                            con.execute("INSERT INTO inmuebles (id_bloque, tipo, precio_alquiler, costo_contrato, deposito_base) VALUES (?,?,?,?,?)", 
                                        (idb, tp, limpiar_monto(pr_t), limpiar_monto(co_t), limpiar_monto(de_t)))
                            con.commit()
                            st.success("Creado")
                            st.rerun()
                        finally:
                            con.close()
        
        with col_b:
            st.write("### ✏️ Editar Precios")
            inm_ex = pd.read_sql_query("SELECT i.id, b.nombre || ' - ' || i.tipo as disp FROM inmuebles i JOIN bloques b ON i.id_bloque = b.id", con)
            if not inm_ex.empty:
                id_ed = st.selectbox("Unidad a editar", inm_ex['id'].tolist(), format_func=lambda x: inm_ex[inm_ex['id']==x]['disp'].values[0])
                curr = pd.read_sql_query(f"SELECT * FROM inmuebles WHERE id={id_ed}", con).iloc[0]
                with st.form("f_edit"):
                    n_pr = st.text_input("Nuevo Alquiler", value=str(int(curr['precio_alquiler'])))
                    n_co = st.text_input("Nuevo Contrato", value=str(int(curr['costo_contrato'])))
                    n_de = st.text_input("Nuevo Depósito", value=str(int(curr['deposito_base'])))
                    if st.form_submit_button("Actualizar"):
                        try:
                            con.execute("UPDATE inmuebles SET precio_alquiler=?, costo_contrato=?, deposito_base=? WHERE id=?", 
                                        (limpiar_monto(n_pr), limpiar_monto(n_co), limpiar_monto(n_de), id_ed))
                            con.commit()
                            st.success("Actualizado")
                            st.rerun()
                        finally:
                            con.close()
        con.close()

    with t1:
        with st.form("f_inq"):
            nom = st.text_input("Nombre"); tel = st.text_input("Celular")
            if st.form_submit_button("Guardar Inquilino"):
                con = conectar()
                con.execute("INSERT INTO inquilinos (nombre, celular) VALUES (?,?)", (nom, tel))
                con.commit(); con.close(); st.rerun()
    with t2:
        with st.form("f_bl"):
            nb = st.text_input("Nombre Bloque")
            if st.form_submit_button("Guardar Bloque"):
                con = conectar()
                con.execute("INSERT INTO bloques (nombre) VALUES (?)", (nb,))
                con.commit(); con.close(); st.rerun()
    with t4:
        st.write("### Generación Masiva")
        mes = st.text_input("Mes/Año (Ej: Junio 2025)")
        if st.button("🚀 Generar"):
            con = conectar()
            activos = pd.read_sql_query("SELECT id, monto_alquiler FROM contratos WHERE activo=1", con)
            for _, c in activos.iterrows():
                con.execute("INSERT INTO deudas (id_contrato, concepto, mes_anio, monto_debe) VALUES (?,?,?,?)", (c['id'], "Alquiler", mes, c['monto_alquiler']))
            con.commit(); con.close(); st.success("Generado")
