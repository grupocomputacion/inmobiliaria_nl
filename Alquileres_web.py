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
# 1. INVENTARIO INTELIGENTE (BASADO EN FECHAS DE CONTRATO)
# ---------------------------------------------------------
if menu == "🏠 Inventario":
    st.subheader("Estado y Disponibilidad Predictiva")
    conn = conectar()
    hoy = date.today()

    # --- LÓGICA DE FILTROS ---
    f1, f2, f3 = st.columns([2, 2, 2])
    filtro_estado = f1.selectbox("Estado Actual", ["TODOS", "Libre Ahora", "Ocupado Ahora"])
    
    bloques_db = pd.read_sql_query("SELECT id, nombre FROM bloques", conn)
    filtro_bloque = f2.selectbox("Filtrar por Bloque", ["TODOS"] + bloques_db['nombre'].tolist())
    
    busqueda = f3.text_input("Buscar Unidad...")

    # --- QUERY MAESTRA ---
    # Traemos los inmuebles y el contrato activo más reciente si existe
    query_base = """
        SELECT 
            i.id, 
            b.nombre as Bloque, 
            i.tipo as Unidad, 
            c.fecha_inicio, 
            c.meses,
            i.precio_alquiler
        FROM inmuebles i
        JOIN bloques b ON i.id_bloque = b.id
        LEFT JOIN contratos c ON i.id = c.id_inmueble AND c.activo = 1
    """
    
    df_raw = pd.read_sql_query(query_base, conn)

    # --- CÁLCULO DE ESTADOS DINÁMICOS ---
    def calcular_disponibilidad(row):
        if pd.isna(row['fecha_inicio']):
            return "Libre", "Inmediata"
        
        # Calculamos fecha de fin: inicio + meses
        try:
            inicio = datetime.strptime(row['fecha_inicio'], '%Y-%m-%d').date()
            fin = inicio + timedelta(days=row['meses'] * 30) # Estimación de meses
            
            if hoy < inicio:
                return "Libre (Reservado)", inicio.strftime('%d/%m/%Y')
            elif hoy <= fin:
                return "Ocupado", fin.strftime('%d/%m/%Y')
            else:
                return "Libre (Contrato Vencido)", "Inmediata"
        except:
            return "Error Datos", "Consultar"

    # Aplicamos la lógica a cada fila
    df_raw[['Estado Real', 'Disponible Desde']] = df_raw.apply(
        lambda x: pd.Series(calcular_disponibilidad(x)), axis=1
    )

    # --- APLICACIÓN DE FILTROS POST-CÁLCULO ---
    df_final = df_raw.copy()
    
    if filtro_estado == "Libre Ahora":
        df_final = df_final[df_final['Estado Real'].str.contains("Libre")]
    elif filtro_estado == "Ocupado Ahora":
        df_final = df_final[df_final['Estado Real'] == "Ocupado"]
        
    if filtro_bloque != "TODOS":
        df_final = df_final[df_final['Bloque'] == filtro_bloque]
        
    if busqueda:
        df_final = df_final[df_final['Unidad'].str.contains(busqueda, case=False)]

    # --- VISUALIZACIÓN ---
    if not df_final.empty:
        # Estilo para iPad: Colores claros y legibles
        def style_estado(val):
            if "Libre" in val: color = '#2ecc71'
            elif "Ocupado" in val: color = '#e74c3c'
            else: color = '#f39c12'
            return f'color: {color}; font-weight: bold'

        # Mostramos columnas relevantes
        cols_mostrar = ["Bloque", "Unidad", "Estado Real", "Disponible Desde", "precio_alquiler"]
        st.dataframe(
            df_final[cols_mostrar].style.applymap(style_estado, subset=['Estado Real']),
            use_container_width=True,
            hide_index=True
        )
        
        # VENTANA DE FUTURO (Punto 2 del requerimiento)
        st.divider()
        st.write("### 📅 Próximas Liberaciones")
        # Filtramos los que se liberan en los próximos 60 días
        df_futuro = df_final[df_final['Estado Real'] == "Ocupado"].sort_values(by="Disponible Desde")
        if not df_futuro.empty:
            for _, r in df_futuro.head(5).iterrows():
                st.info(f"La unidad **{r['Unidad']}** ({r['Bloque']}) se liberará el **{r['Disponible Desde']}**")
        else:
            st.success("No hay liberaciones programadas en el corto plazo.")
            
    else:
        st.warning("No hay inmuebles que coincidan con la búsqueda.")

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
