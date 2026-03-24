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
    # Timeout alto para evitar bloqueos en Streamlit Cloud
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

def crear_db_si_no_existe():
    """Crea el esquema completo con todas las columnas necesarias"""
    conn = conectar()
    c = conn.cursor()
    c.executescript('''
        CREATE TABLE IF NOT EXISTS bloques (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT UNIQUE);
        CREATE TABLE IF NOT EXISTS inmuebles (
            id INTEGER PRIMARY KEY AUTOINCREMENT, id_bloque INTEGER, tipo TEXT, 
            precio_alquiler REAL, costo_contrato REAL, deposito_base REAL,
            UNIQUE(id_bloque, tipo)
        );
        CREATE TABLE IF NOT EXISTS inquilinos (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT, celular TEXT);
        CREATE TABLE IF NOT EXISTS contratos (
            id INTEGER PRIMARY KEY AUTOINCREMENT, id_inmueble INTEGER, id_inquilino INTEGER, 
            fecha_inicio DATE, fecha_fin DATE, meses INTEGER, activo INTEGER DEFAULT 1, 
            monto_alquiler REAL, monto_contrato REAL, monto_deposito REAL
        );
        CREATE TABLE IF NOT EXISTS deudas (
            id INTEGER PRIMARY KEY AUTOINCREMENT, id_contrato INTEGER, concepto TEXT, 
            mes_anio TEXT, monto_debe REAL, monto_pago REAL DEFAULT 0, pagado INTEGER DEFAULT 0, fecha_cobro DATE
        );
    ''')
    conn.commit()
    conn.close()

def vaciar_base_de_datos():
    """Borra todos los registros de todas las tablas de forma segura"""
    conn = conectar()
    c = conn.cursor()
    tablas = ["deudas", "contratos", "inquilinos", "inmuebles", "bloques"]
    for t in tablas:
        try:
            c.execute(f"DELETE FROM {t}")
            c.execute(f"UPDATE sqlite_sequence SET seq = 0 WHERE name = '{t}'")
        except:
            pass
    conn.commit()
    conn.close()

# Inicialización obligatoria
crear_db_si_no_existe()

# --- 3. MENÚ LATERAL ---
with st.sidebar:
    st.title("🏢 Inmobiliaria Pro")
    if st.button("🚨 REINICIAR TODA LA BASE (BORRADO TOTAL)"):
        vaciar_base_de_datos()
        st.cache_data.clear()
        st.success("¡Base de datos vaciada por completo!")
        st.rerun()
    
    st.divider()
    menu = st.radio(
        "Navegación:",
        ["🏠 1. Inventario", "📝 2. Nuevo Contrato", "💰 3. Cobranzas", "🚨 4. Morosos", "📊 5. Caja", "⚙️ 6. Maestros"],
        label_visibility="collapsed"
    )

# ---------------------------------------------------------
# 1. INVENTARIO (SIN DUPLICADOS)
# ---------------------------------------------------------
if menu == "🏠 1. Inventario":
    st.subheader("Estado de Unidades")
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
                cur = con.cursor()
                cur.execute("INSERT INTO contratos (id_inmueble, id_inquilino, fecha_inicio, fecha_fin, meses, activo, monto_alquiler, monto_contrato, monto_deposito) VALUES (?,?,?,?,?,1,?,?,?)", 
                            (id_inm, id_inq, f_ini, f_fin, meses, limpiar_monto(m_alq_t), limpiar_monto(m_con_t), limpiar_monto(m_dep_t)))
                con.commit(); con.close(); st.success("Contrato grabado"); st.rerun()

# ---------------------------------------------------------
# 3. COBRANZAS
# ---------------------------------------------------------
elif menu == "💰 3. Cobranzas":
    st.subheader("Gestión de Cobros")
    conn = conectar()
    df_c = pd.read_sql_query("SELECT d.id, i.tipo, inq.nombre, d.monto_debe, d.monto_pago, inq.celular, d.concepto FROM deudas d JOIN contratos c ON d.id_contrato=c.id JOIN inmuebles i ON c.id_inmueble=i.id JOIN inquilinos inq ON c.id_inquilino=inq.id WHERE d.pagado = 0", conn)
    for _, row in df_c.iterrows():
        with st.expander(f"{row['tipo']} - {row['nombre']}"):
            saldo = row['monto_debe'] - row['monto_pago']
            st.write(f"Debe: {fmt_moneda(saldo)}")
            p_t = st.text_input("Cobrar", value=str(int(saldo)), key=f"c_{row['id']}")
            if st.button("Confirmar", key=f"b_{row['id']}"):
                con = conectar(); p = limpiar_monto(p_t)
                nuevo = row['monto_pago'] + p
                pagado = 1 if nuevo >= row['monto_debe'] else 0
                con.execute("UPDATE deudas SET monto_pago=?, pagado=?, fecha_cobro=? WHERE id=?", (nuevo, pagado, date.today(), row['id']))
                con.commit(); con.close()
                msg = urllib.parse.quote(f"✅ RECIBO: {row['tipo']}\\nAbonado: {fmt_moneda(p)}\\nSaldo: {fmt_moneda(saldo-p)}")
                st.markdown(f'<a href="https://wa.me/{row["celular"]}?text={msg}" target="_blank">📲 WhatsApp</a>', unsafe_allow_html=True)
                st.rerun()
    conn.close()

# ---------------------------------------------------------
# 4. MOROSOS / 5. CAJA
# ---------------------------------------------------------
elif menu == "🚨 4. Morosos":
    st.subheader("Deudores")
    df_m = pd.read_sql_query("SELECT inq.nombre as Inquilino, i.tipo as Unidad, (d.monto_debe - d.monto_pago) as Saldo FROM deudas d JOIN contratos c ON d.id_contrato=c.id JOIN inmuebles i ON c.id_inmueble=i.id JOIN inquilinos inq ON c.id_inquilino=inq.id WHERE d.pagado = 0", conectar())
    if not df_m.empty:
        st.error(f"Mora Total: {fmt_moneda(df_m['Saldo'].sum())}")
        st.table(df_m)

elif menu == "📊 5. Caja":
    st.subheader("Caja")
    df_cj = pd.read_sql_query("SELECT fecha_cobro as Fecha, concepto as Detalle, monto_pago as Monto FROM deudas WHERE pagado=1", conectar())
    if not df_cj.empty:
        st.metric("Total", fmt_moneda(df_cj['Monto'].sum()))
        st.table(df_cj)

# ---------------------------------------------------------
# 6. MAESTROS (CON EDICIÓN Y ELIMINACIÓN DE INQUILINOS)
# ---------------------------------------------------------
elif menu == "⚙️ 6. Maestros":
    st.subheader("Administración de Maestros")
    t1, t2, t3, t4 = st.tabs(["👤 Inquilinos", "🏢 Bloques", "🏠 Unidades", "⚡ Procesos"])
    
    with t1:
        con = conectar()
        col1, col2 = st.columns(2)
        with col1:
            st.write("### ➕ Nuevo Inquilino")
            with st.form("f_inq"):
                nom = st.text_input("Nombre"); tel = st.text_input("WhatsApp (549...)")
                if st.form_submit_button("Guardar"):
                    con.execute("INSERT INTO inquilinos (nombre, celular) VALUES (?,?)", (nom, tel))
                    con.commit(); st.rerun()
        with col2:
            st.write("### ✏️ Editar / 🗑️ Eliminar")
            inqs = pd.read_sql_query("SELECT * FROM inquilinos", con)
            if not inqs.empty:
                id_i = st.selectbox("Inquilino", inqs['id'].tolist(), format_func=lambda x: inqs[inqs['id']==x]['nombre'].values[0])
                curr_i = inqs[inqs['id']==id_i].iloc[0]
                
                with st.form("f_inq_edit"):
                    n_nom = st.text_input("Nombre", value=curr_i['nombre'])
                    n_tel = st.text_input("Celular", value=curr_i['celular'])
                    c_btn1, c_btn2 = st.columns(2)
                    if c_btn1.form_submit_button("✅ Actualizar"):
                        con.execute("UPDATE inquilinos SET nombre=?, celular=? WHERE id=?", (n_nom, n_tel, id_i))
                        con.commit(); st.success("Actualizado"); st.rerun()
                    if c_btn2.form_submit_button("🗑️ ELIMINAR"):
                        con.execute("DELETE FROM inquilinos WHERE id=?", (id_i,))
                        con.commit(); st.warning("Eliminado"); st.rerun()
        
        st.write("---")
        st.write("### Listado Actual")
        st.dataframe(inqs[["nombre", "celular"]], use_container_width=True, hide_index=True)
        con.close()

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
                        con.execute("INSERT INTO inmuebles (id_bloque, tipo, precio_alquiler, costo_contrato, deposito_base) VALUES (?,?,?,?,?)", (idb, tp, limpiar_monto(pr_t), limpiar_monto(co_t), limpiar_monto(de_t)))
                        con.commit(); st.rerun()
        with col_b:
            st.write("### ✏️ Editar Precios / 🗑️ Borrar")
            inm_ex = pd.read_sql_query("SELECT i.id, b.nombre || ' - ' || i.tipo as disp FROM inmuebles i JOIN bloques b ON i.id_bloque = b.id", con)
            if not inm_ex.empty:
                id_ed = st.selectbox("Unidad", inm_ex['id'].tolist(), format_func=lambda x: inm_ex[inm_ex['id']==x]['disp'].values[0])
                curr = pd.read_sql_query(f"SELECT * FROM inmuebles WHERE id={id_ed}", con).iloc[0]
                with st.form("f_edit"):
                    n_pr = st.text_input("Nuevo Alquiler", value=str(int(curr['precio_alquiler'])))
                    n_co = st.text_input("Nuevo Contrato", value=str(int(curr['costo_contrato'])))
                    n_de = st.text_input("Nuevo Depósito", value=str(int(curr['deposito_base'])))
                    cb1, cb2 = st.columns(2)
                    if cb1.form_submit_button("✅ Actualizar"):
                        con.execute("UPDATE inmuebles SET precio_alquiler=?, costo_contrato=?, deposito_base=? WHERE id=?", (limpiar_monto(n_pr), limpiar_monto(n_co), limpiar_monto(n_de), id_ed))
                        con.commit(); st.rerun()
                    if cb2.form_submit_button("🗑️ Borrar Unidad"):
                        con.execute("DELETE FROM inmuebles WHERE id=?", (id_ed,))
                        con.commit(); st.rerun()
        con.close()
