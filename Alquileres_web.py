import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, date, timedelta
import urllib.parse
import os

# ==========================================
# 1. CONFIGURACIÓN Y MOTOR DE BASE DE DATOS
# ==========================================
st.set_page_config(page_title="Inmobiliaria Pro Cloud", layout="wide", initial_sidebar_state="expanded")

def conectar():
    return sqlite3.connect('datos_alquileres.db', check_same_thread=False, timeout=20)

def fmt_moneda(valor):
    try: return f"$ {int(float(valor or 0)):,}".replace(",", ".")
    except: return "$ 0"

def limpiar_monto(texto):
    if not texto: return 0.0
    try: return float(str(texto).replace('$', '').replace('.', '').replace(',', '').strip())
    except: return 0.0

def inicializar_absoluto():
    if os.path.exists('datos_alquileres.db'):
        os.remove('datos_alquileres.db')
    conn = conectar()
    c = conn.cursor()
    c.executescript('''
        CREATE TABLE bloques (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT UNIQUE);
        CREATE TABLE inmuebles (
            id INTEGER PRIMARY KEY AUTOINCREMENT, id_bloque INTEGER, tipo TEXT, 
            precio_alquiler REAL, costo_contrato REAL, deposito_base REAL, UNIQUE(id_bloque, tipo)
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

# ==========================================
# 2. MENÚ LATERAL
# ==========================================
with st.sidebar:
    st.title("🏢 Inmobiliaria Pro")
    if st.button("🚨 REINICIAR TODA LA BASE"):
        inicializar_absoluto()
        st.cache_data.clear()
        st.rerun()
    st.divider()
    menu = st.radio("Navegación:", 
                    ["🏠 1. Inventario", "📝 2. Nuevo Contrato", "💰 3. Cobranzas", 
                     "🚨 4. Morosos", "📊 5. Caja", "⚙️ 6. Maestros"], 
                    label_visibility="collapsed")

# ==========================================
# 1. FUNCIONALIDAD: INVENTARIO (CON ESTADOS)
# ==========================================
if menu == "🏠 1. Inventario":
    st.subheader("Estado de Unidades y Disponibilidad")
    conn = conectar()
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
            hoy = date.today()
            if pd.isna(row['fecha_inicio']) or row['activo'] == 0: return "Libre", "LIBRE HOY"
            try:
                f_fin = pd.to_datetime(row['fecha_fin']).date()
                if hoy <= f_fin: return "OCUPADO", f_fin.strftime('%d/%m/%Y')
                else: return "VENCIDO", "LIBRE HOY"
            except: return "Libre", "LIBRE HOY"

        df[['Situación', 'Disponible Desde']] = df.apply(lambda x: pd.Series(calc_sit(x)), axis=1)
        df['Alquiler'] = df['precio_alquiler'].apply(fmt_moneda)
        df['Contrato'] = df['costo_contrato'].apply(fmt_moneda)
        df['Depósito'] = df['deposito_base'].apply(fmt_moneda)
        
        def color_sit(val):
            color = '#28a745' if val == "Libre" else '#dc3545' if val == "OCUPADO" else '#fd7e14'
            return f'color: {color}; font-weight: bold'

        st.dataframe(df[["Bloque", "Unidad", "Situación", "Disponible Desde", "Alquiler", "Contrato", "Depósito"]].style.applymap(color_sit, subset=['Situación']), 
                     use_container_width=True, hide_index=True)
    else: st.info("Cargue unidades en Maestros.")

# ==========================================
# 2. FUNCIONALIDAD: NUEVO CONTRATO
# ==========================================
elif menu == "📝 2. Nuevo Contrato":
    st.subheader("Alta de Alquiler")
    conn = conectar()
    inm_db = pd.read_sql_query("SELECT * FROM inmuebles", conn)
    inq_db = pd.read_sql_query("SELECT * FROM inquilinos", conn)
    if not inm_db.empty and not inq_db.empty:
        with st.form("f_con"):
            c1, c2 = st.columns(2)
            id_inm = c1.selectbox("Unidad", inm_db['id'].tolist(), format_func=lambda x: f"{inm_db[inm_db['id']==x]['tipo'].values[0]}")
            id_inq = c2.selectbox("Inquilino", inq_db['id'].tolist(), format_func=lambda x: inq_db[inq_db['id']==x]['nombre'].values[0])
            f_ini = c1.date_input("Inicio", date.today())
            meses = c2.number_input("Meses", min_value=1, value=6)
            f_fin = f_ini + timedelta(days=meses * 30)
            val_ref = inm_db[inm_db['id'] == id_inm].iloc[0]
            m_alq = c1.text_input("Alquiler Mensual", value=str(int(val_ref['precio_alquiler'])))
            m_con = c2.text_input("Costo Contrato", value=str(int(val_ref['costo_contrato'])))
            m_dep = c1.text_input("Depósito", value=str(int(val_ref['deposito_base'])))
            if st.form_submit_button("Grabar Contrato"):
                conn.execute("INSERT INTO contratos (id_inmueble, id_inquilino, fecha_inicio, fecha_fin, meses, activo, monto_alquiler, monto_contrato, monto_deposito) VALUES (?,?,?,?,?,1,?,?,?)", 
                            (id_inm, id_inq, f_ini, f_fin, meses, limpiar_monto(m_alq), limpiar_monto(m_con), limpiar_monto(m_dep)))
                conn.commit(); st.success("Contrato grabado"); st.rerun()
    else: st.warning("Faltan datos en Maestros.")
    conn.close()

# ==========================================
# 3. FUNCIONALIDAD: COBRANZAS (WHATSAPP)
# ==========================================
elif menu == "💰 3. Cobranzas":
    st.subheader("Gestión de Cobros")
    conn = conectar()
    df_c = pd.read_sql_query("""
        SELECT d.id, i.tipo, inq.nombre, d.monto_debe, d.monto_pago, inq.celular, d.concepto
        FROM deudas d JOIN contratos c ON d.id_contrato=c.id
        JOIN inmuebles i ON c.id_inmueble=i.id JOIN inquilinos inq ON c.id_inquilino=inq.id
        WHERE d.pagado = 0
    """, conn)
    for _, row in df_c.iterrows():
        with st.expander(f"{row['tipo']} - {row['nombre']}"):
            saldo = row['monto_debe'] - row['monto_pago']
            pago_t = st.text_input(f"Cobrar a {row['nombre']}", value=str(int(saldo)), key=f"c_{row['id']}")
            if st.button("Confirmar Pago", key=f"b_{row['id']}"):
                p = limpiar_monto(pago_t)
                conn.execute("UPDATE deudas SET monto_pago=?, pagado=? WHERE id=?", (row['monto_pago']+p, 1 if (row['monto_pago']+p)>=row['monto_debe'] else 0, row['id']))
                conn.commit()
                msg = urllib.parse.quote(f"✅ RECIBO: {row['tipo']}\nAbonado: {fmt_moneda(p)}\nSaldo: {fmt_moneda(saldo-p)}")
                st.markdown(f'''<a href="https://wa.me/{row["celular"]}?text={msg}" target="_blank"><button style="background-color:#25D366; color:white; border:none; padding:10px; border-radius:8px; width:100%; cursor:pointer;">📲 Enviar WhatsApp</button></a>''', unsafe_allow_html=True)
    conn.close()

# ==========================================
# 4. MOROSOS Y 5. CAJA
# ==========================================
elif menu == "🚨 4. Morosos":
    st.subheader("Deudores")
    conn = conectar()
    df_m = pd.read_sql_query("SELECT inq.nombre as Inquilino, i.tipo as Unidad, (d.monto_debe - d.monto_pago) as Saldo FROM deudas d JOIN contratos c ON d.id_contrato=c.id JOIN inmuebles i ON c.id_inmueble=i.id JOIN inquilinos inq ON c.id_inquilino=inq.id WHERE d.pagado=0", conn)
    if not df_m.empty: st.table(df_m)
    else: st.success("Al día.")
    conn.close()

elif menu == "📊 5. Caja":
    st.subheader("Ingresos")
    df_cj = pd.read_sql_query("SELECT fecha_cobro, concepto, monto_pago FROM deudas WHERE pagado=1", conectar())
    if not df_cj.empty: st.dataframe(df_cj, use_container_width=True)

# ==========================================
# 6. FUNCIONALIDAD: MAESTROS (EDICIÓN COMPLETA)
# ==========================================
elif menu == "⚙️ 6. Maestros":
    st.subheader("Administración de Maestros")
    t1, t2, t3, t4 = st.tabs(["👤 Inquilinos", "🏢 Bloques", "🏠 Unidades", "⚡ Procesos"])
    
    with t1:
        con = conectar()
        col1, col2 = st.columns(2)
        with col1:
            st.write("### ➕ Nuevo")
            with st.form("fi"):
                n, t = st.text_input("Nombre"), st.text_input("WhatsApp")
                if st.form_submit_button("Guardar"):
                    con.execute("INSERT INTO inquilinos (nombre, celular) VALUES (?,?)", (n, t))
                    con.commit(); st.rerun()
        with col2:
            st.write("### ✏️ Editar/Borrar")
            inqs = pd.read_sql_query("SELECT * FROM inquilinos", con)
            if not inqs.empty:
                id_i = st.selectbox("Inquilino", inqs['id'].tolist(), format_func=lambda x: inqs[inqs['id']==x]['nombre'].values[0])
                cur_i = inqs[inqs['id']==id_i].iloc[0]
                with st.form("fe_i"):
                    en, et = st.text_input("Nombre", cur_i['nombre']), st.text_input("WhatsApp", cur_i['celular'])
                    b1, b2 = st.columns(2)
                    if b1.form_submit_button("Actualizar"):
                        con.execute("UPDATE inquilinos SET nombre=?, celular=? WHERE id=?", (en, et, id_i))
                        con.commit(); st.rerun()
                    if b2.form_submit_button("ELIMINAR"):
                        con.execute("DELETE FROM inquilinos WHERE id=?", (id_i,))
                        con.commit(); st.rerun()
        con.close()

    with t3:
        con = conectar()
        bls = pd.read_sql_query("SELECT * FROM bloques", con)
        c_a, c_b = st.columns(2)
        with c_a:
            st.write("### ➕ Nueva Unidad")
            if not bls.empty:
                with st.form("f_u"):
                    idb = st.selectbox("Bloque", bls['id'].tolist(), format_func=lambda x: bls[bls['id']==x]['nombre'].values[0])
                    tp, pr, co, de = st.text_input("Unidad"), st.text_input("Alquiler"), st.text_input("Contrato"), st.text_input("Depósito")
                    if st.form_submit_button("Guardar"):
                        con.execute("INSERT INTO inmuebles (id_bloque, tipo, precio_alquiler, costo_contrato, deposito_base) VALUES (?,?,?,?,?)", (idb, tp, limpiar_monto(pr), limpiar_monto(co), limpiar_monto(de)))
                        con.commit(); st.rerun()
        with c_b:
            st.write("### ✏️ Editar Precios")
            inm_ex = pd.read_sql_query("SELECT i.id, b.nombre || ' - ' || i.tipo as disp FROM inmuebles i JOIN bloques b ON i.id_bloque = b.id", con)
            if not inm_ex.empty:
                id_ed = st.selectbox("Unidad", inm_ex['id'].tolist(), format_func=lambda x: inm_ex[inm_ex['id']==x]['disp'].values[0])
                cur = pd.read_sql_query(f"SELECT * FROM inmuebles WHERE id={id_ed}", con).iloc[0]
                with st.form("f_eu"):
                    e_pr, e_co, e_de = st.text_input("Alquiler", str(int(cur['precio_alquiler']))), st.text_input("Contrato", str(int(cur['costo_contrato']))), st.text_input("Depósito", str(int(cur['deposito_base'])))
                    if st.form_submit_button("Actualizar"):
                        con.execute("UPDATE inmuebles SET precio_alquiler=?, costo_contrato=?, deposito_base=? WHERE id=?", (limpiar_monto(e_pr), limpiar_monto(e_co), limpiar_monto(e_de), id_ed))
                        con.commit(); st.rerun()
        con.close()

    with t4:
        st.write("### Procesos Masivos")
        mes = st.text_input("Mes/Año (Ej: Junio 2025)")
        if st.button("🚀 Generar"):
            con = conectar()
            activos = pd.read_sql_query("SELECT id, monto_alquiler FROM contratos WHERE activo=1", con)
            for _, c in activos.iterrows():
                con.execute("INSERT INTO deudas (id_contrato, concepto, mes_anio, monto_debe) VALUES (?,?,?,?)", (c['id'], "Alquiler", mes, c['monto_alquiler']))
            con.commit(); con.close(); st.success("Generado")
