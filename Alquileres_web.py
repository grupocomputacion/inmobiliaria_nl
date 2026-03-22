import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import urllib.parse

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Inmobiliaria Pro Cloud", layout="wide")

# --- CONEXIÓN DB ---
def conectar():
    return sqlite3.connect('datos_alquileres.db', check_same_thread=False)

def init_db():
    conn = conectar()
    c = conn.cursor()
    # Mantenemos la estructura exacta de tu archivo Alquileres.py
    c.executescript('''
        CREATE TABLE IF NOT EXISTS bloques (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT UNIQUE);
        CREATE TABLE IF NOT EXISTS inmuebles (id INTEGER PRIMARY KEY AUTOINCREMENT, id_bloque INTEGER, tipo TEXT, precio_alquiler REAL, costo_contrato REAL, deposito_base REAL, estado TEXT DEFAULT 'Libre');
        CREATE TABLE IF NOT EXISTS inquilinos (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT, celular TEXT, procedencia TEXT, grupo TEXT, em_nombre TEXT, em_tel TEXT);
        CREATE TABLE IF NOT EXISTS contratos (id INTEGER PRIMARY KEY AUTOINCREMENT, id_inmueble INTEGER, id_inquilino INTEGER, fecha_inicio DATE, meses INTEGER, activo INTEGER DEFAULT 1, monto_alquiler REAL, monto_contrato REAL, monto_deposito REAL);
        CREATE TABLE IF NOT EXISTS deudas (id INTEGER PRIMARY KEY AUTOINCREMENT, id_contrato INTEGER, concepto TEXT, mes_anio TEXT, monto_debe REAL, monto_pago REAL DEFAULT 0, pagado INTEGER DEFAULT 0, fecha_cobro DATE);
    ''')
    conn.commit()
    conn.close()

init_db()

# --- FUNCIONES AUXILIARES ---
def fmt_moneda(valor):
    try: return f"$ {int(float(valor or 0)):,}".replace(",", ".")
    except: return "$ 0"

def crear_link_whatsapp(telefono, mensaje):
    # Limpiar teléfono (solo números)
    tel_limpio = "".join(filter(str.isdigit, str(telefono)))
    mensaje_enc = urllib.parse.quote(mensaje)
    return f"https://wa.me/{tel_limpio}?text={mensaje_enc}"

# --- INTERFAZ ---
st.title("🏢 Gestión Inmobiliaria Pro - Cloud Edition")

menu = st.sidebar.selectbox("MENÚ", ["🏠 Inventario", "✍️ Contratos", "📋 Cobranzas", "📊 Caja"])

# ---------------------------------------------------------
# 1. INVENTARIO
# ---------------------------------------------------------
if menu == "🏠 Inventario":
    col_form, col_tabla = st.columns([1, 2])
    
    with col_form:
        st.subheader("Configuración")
        with st.expander("➕ Crear Nuevo Bloque"):
            n_bloque = st.text_input("Nombre del Bloque")
            if st.button("Guardar Bloque"):
                conn = conectar()
                try:
                    conn.execute("INSERT INTO bloques (nombre) VALUES (?)", (n_bloque,))
                    conn.commit()
                    st.success("Bloque creado")
                except: st.error("Error: El bloque ya existe")

        st.divider()
        st.subheader("Nueva Unidad")
        conn = conectar()
        bloques = pd.read_sql_query("SELECT * FROM bloques", conn)
        
        if not bloques.empty:
            b_sel = st.selectbox("Bloque", bloques['nombre'].tolist())
            id_b = bloques[bloques['nombre'] == b_sel]['id'].values[0]
            tipo = st.text_input("Nombre Unidad (Ej: Depto 1)")
            alquiler = st.number_input("Precio Alquiler $", min_value=0.0)
            contrato = st.number_input("Costo Contrato $", min_value=0.0)
            deposito = st.number_input("Depósito Base $", min_value=0.0)
            
            if st.button("💾 Guardar Unidad"):
                conn.execute("INSERT INTO inmuebles (id_bloque, tipo, precio_alquiler, costo_contrato, deposito_base) VALUES (?,?,?,?,?)",
                            (int(id_b), tipo, alquiler, contrato, deposito))
                conn.commit()
                st.success("Unidad guardada")
                st.rerun()

    with col_tabla:
        st.subheader("Listado de Unidades")
        df_inm = pd.read_sql_query("""
            SELECT i.id, b.nombre as Bloque, i.tipo as Unidad, i.precio_alquiler as Alquiler, i.estado as Estado 
            FROM inmuebles i JOIN bloques b ON i.id_bloque = b.id""", conectar())
        st.dataframe(df_inm, use_container_width=True)

# ---------------------------------------------------------
# 2. CONTRATOS (Generación automática de deudas)
# ---------------------------------------------------------
elif menu == "✍️ Contratos":
    st.subheader("Nuevo Contrato")
    conn = conectar()
    libres = pd.read_sql_query("SELECT i.id, b.nombre || ' - ' || i.tipo as unidad FROM inmuebles i JOIN bloques b ON i.id_bloque=b.id WHERE i.estado='Libre'", conn)
    
    if not libres.empty:
        c1, c2 = st.columns(2)
        unidad_sel = c1.selectbox("Unidad Libre", libres['unidad'].tolist())
        id_i = int(libres[libres['unidad'] == unidad_sel]['id'].values[0])
        meses = c2.number_input("Meses", min_value=1, value=6)
        
        st.write("#### Datos del Inquilino")
        col_inq = st.columns(3)
        nom = col_inq[0].text_input("Nombre")
        cel = col_inq[1].text_input("Celular (Con código de área)")
        proc = col_inq[2].text_input("Procedencia")
        
        if st.button("🤝 GENERAR CONTRATO"):
            c = conn.cursor()
            c.execute("SELECT precio_alquiler, costo_contrato, deposito_base FROM inmuebles WHERE id=?", (id_i,))
            p = c.fetchone()
            
            c.execute("INSERT INTO inquilinos (nombre, celular, procedencia) VALUES (?,?,?)", (nom, cel, proc))
            id_q = c.lastrowid
            
            c.execute("""INSERT INTO contratos (id_inmueble, id_inquilino, fecha_inicio, meses, monto_alquiler, monto_contrato, monto_deposito) 
                         VALUES (?,?,?,?,?,?,?)""", (id_i, id_q, datetime.now().strftime('%Y-%m-%d'), meses, p[0], p[1], p[2]))
            id_con = c.lastrowid
            
            # Generación de deudas según tu lógica original
            c.execute("INSERT INTO deudas (id_contrato, concepto, mes_anio, monto_debe) VALUES (?, 'Contrato', 'Unico', ?)", (id_con, p[1]))
            c.execute("INSERT INTO deudas (id_contrato, concepto, mes_anio, monto_debe) VALUES (?, 'Deposito', 'Unico', ?)", (id_con, p[2]))
            for m in range(meses):
                f_venc = (datetime.now() + timedelta(days=30*m)).strftime('%m-%Y')
                c.execute("INSERT INTO deudas (id_contrato, concepto, mes_anio, monto_debe) VALUES (?, 'Alquiler', ?, ?)", (id_con, f_venc, p[0]))
            
            c.execute("UPDATE inmuebles SET estado='Ocupado' WHERE id=?", (id_i,))
            conn.commit()
            
            msg_wa = f"Hola {nom}, se ha generado el contrato #{id_con} por la unidad {unidad_sel}.\nAlquiler: {fmt_moneda(p[0])}\nDepósito: {fmt_moneda(p[2])}"
            url_wa = crear_link_whatsapp(cel, msg_wa)
            st.success("Contrato Generado con éxito.")
            st.markdown(f'''<a href="{url_wa}" target="_blank"><button style="background-color:#25D366; color:white; border:none; padding:10px 20px; border-radius:5px; cursor:pointer;">📲 Enviar Notificación por WhatsApp</button></a>''', unsafe_allow_html=True)

# ---------------------------------------------------------
# 3. COBRANZAS (Pagos y Recibos WA)
# ---------------------------------------------------------
elif menu == "📋 Cobranzas":
    st.subheader("Cobros y Recibos")
    conn = conectar()
    search = st.text_input("Buscar por Nombre o Contrato #")
    
    query_inq = "SELECT c.id, i.nombre, i.celular FROM contratos c JOIN inquilinos i ON c.id_inquilino = i.id WHERE c.activo = 1"
    if search: query_inq += f" AND (i.nombre LIKE '%{search}%' OR c.id LIKE '%{search}%')"
    
    df_inqs = pd.read_sql_query(query_inq, conn)
    
    if not df_inqs.empty:
        sel = st.selectbox("Seleccionar Inquilino", df_inqs.apply(lambda r: f"#{r['id']} | {r['nombre']}", axis=1))
        id_con = int(sel.split("|")[0].replace("#", "").strip())
        tel_inq = df_inqs[df_inqs['id'] == id_con]['celular'].values[0]
        nom_inq = df_inqs[df_inqs['id'] == id_con]['nombre'].values[0]

        deudas = pd.read_sql_query(f"SELECT id, concepto, mes_anio, monto_debe, monto_pago, (monto_debe - monto_pago) as Saldo FROM deudas WHERE id_contrato={id_con} AND pagado=0", conn)
        
        if not deudas.empty:
            st.dataframe(deudas, use_container_width=True)
            with st.form("pago"):
                id_d = st.selectbox("ID de Deuda a cobrar", deudas['id'].tolist())
                monto = st.number_input("Monto a cobrar $", min_value=0.0)
                if st.form_submit_button("💰 PROCESAR PAGO"):
                    c = conn.cursor()
                    c.execute("SELECT concepto, mes_anio, monto_debe, monto_pago FROM deudas WHERE id=?", (id_d,))
                    d_act = c.fetchone()
                    nuevo_pago = d_act[3] + monto
                    pagado = 1 if nuevo_pago >= d_act[2] else 0
                    
                    c.execute("UPDATE deudas SET monto_pago=?, pagado=?, fecha_cobro=? WHERE id=?", 
                             (nuevo_pago, pagado, datetime.now().strftime('%Y-%m-%d'), id_d))
                    conn.commit()
                    
                    # Generar Recibo para WhatsApp
                    recibo = f"✅ RECIBO DE PAGO\nInquilino: {nom_inq}\nConcepto: {d_act[0]} ({d_act[1]})\nAbonado: {fmt_moneda(monto)}\nFecha: {datetime.now().strftime('%d/%m/%Y')}"
                    st.session_state['last_wa'] = crear_link_whatsapp(tel_inq, recibo)
                    st.success("Pago impactado.")
                    st.rerun()
            
            if 'last_wa' in st.session_state:
                st.markdown(f'''<a href="{st.session_state['last_wa']}" target="_blank"><button style="background-color:#25D366; color:white; border:none; padding:10px 20px; border-radius:5px; cursor:pointer;">📲 Enviar Recibo por WhatsApp</button></a>''', unsafe_allow_html=True)

# ---------------------------------------------------------
# 4. CAJA
# ---------------------------------------------------------
elif menu == "📊 Caja":
    st.subheader("Resumen de Caja")
    df_caja = pd.read_sql_query("""
        SELECT d.fecha_cobro as Fecha, i.tipo as Unidad, d.concepto as Concepto, d.monto_pago as Monto 
        FROM deudas d JOIN contratos c ON d.id_contrato=c.id 
        JOIN inmuebles i ON c.id_inmueble=i.id 
        WHERE d.monto_pago > 0""", conectar())
    
    st.dataframe(df_caja, use_container_width=True)
    st.metric("Total en Caja", fmt_moneda(df_caja['Monto'].sum()))
