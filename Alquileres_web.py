import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, date, timedelta
import urllib.parse
import io

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Inmobiliaria Pro Cloud", layout="wide", initial_sidebar_state="expanded")

# --- FUNCIONES DE MOTOR (RESTAURADAS) ---
def conectar():
    return sqlite3.connect('datos_alquileres.db', check_same_thread=False)

def fmt_moneda(valor):
    """Formatea importes: $ 1.250.000 (Sin decimales, punto de miles)"""
    try:
        return f"$ {int(float(valor)):,}".replace(",", ".")
    except:
        return "$ 0"

def crear_link_whatsapp(tel, mensaje):
    texto = urllib.parse.quote(mensaje)
    return f"https://api.whatsapp.com/send?phone={tel}&text={texto}"

def init_db():
    conn = conectar()
    c = conn.cursor()
    # Mantenemos tu estructura original exacta
    c.executescript('''
        CREATE TABLE IF NOT EXISTS bloques (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT UNIQUE);
        CREATE TABLE IF NOT EXISTS inmuebles (id INTEGER PRIMARY KEY AUTOINCREMENT, id_bloque INTEGER, tipo TEXT, precio_alquiler REAL, costo_contrato REAL, deposito_base REAL, estado TEXT DEFAULT 'Libre');
        CREATE TABLE IF NOT EXISTS inquilinos (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT, celular TEXT, procedencia TEXT, grupo TEXT, em_nombre TEXT, em_tel TEXT);
        CREATE TABLE IF NOT EXISTS contratos (id INTEGER PRIMARY KEY AUTOINCREMENT, id_inmueble INTEGER, id_inquilino INTEGER, fecha_inicio DATE, meses INTEGER, activo INTEGER DEFAULT 1, monto_alquiler REAL, monto_contrato REAL, monto_deposito REAL);
        CREATE TABLE IF NOT EXISTS deudas (id INTEGER PRIMARY KEY AUTOINCREMENT, id_contrato INTEGER, concepto TEXT, mes_anio TEXT, monto_debe REAL, monto_pago REAL DEFAULT 0, pagado INTEGER DEFAULT 0, fecha_cobro DATE);
    ''')
    
    # MIGRACIÓN SEGURA: Agregamos fecha_fin si no existe para la lógica predictiva
    try:
        c.execute("ALTER TABLE contratos ADD COLUMN fecha_fin DATE")
    except:
        pass
    conn.commit()
    conn.close()

def inicializar_total():
    """Reinicio absoluto de la base de datos"""
    conn = conectar()
    c = conn.cursor()
    c.execute("DROP TABLE IF EXISTS deudas")
    c.execute("DROP TABLE IF EXISTS contratos")
    c.execute("DROP TABLE IF EXISTS inquilinos")
    c.execute("DROP TABLE IF EXISTS inmuebles")
    c.execute("DROP TABLE IF EXISTS bloques")
    conn.commit()
    conn.close()
    init_db()

init_db()

# --- MENÚ LATERAL VISUAL CON ICONOS ---
with st.sidebar:
    st.title("🏢 Inmobiliaria Pro")
    if st.button("⚠️ REINICIALIZAR TODO"):
        inicializar_total()
        st.rerun()
    
    st.divider()
    menu = st.radio(
        "Navegación:",
        ["🏠 Inventario", "📝 Nuevo Contrato", "💰 Cobranzas", "🚨 Morosos", "📊 Caja", "⚙️ Configuración"],
        label_visibility="collapsed"
    )

# ---------------------------------------------------------
# 1. INVENTARIO (COLORES Y FECHAS PREDICTIVAS)
# ---------------------------------------------------------
if menu == "🏠 Inventario":
    st.subheader("Estado de Unidades y Disponibilidad")
    conn = conectar()
    hoy = date.today()
    
    query = """
        SELECT i.id, b.nombre as Bloque, i.tipo as Unidad, i.precio_alquiler,
               c.fecha_inicio, c.fecha_fin, c.activo
        FROM inmuebles i
        JOIN bloques b ON i.id_bloque = b.id
        LEFT JOIN contratos c ON i.id = c.id_inmueble AND c.activo = 1
    """
    try:
        df = pd.read_sql_query(query, conn)

        def calcular_estado_visual(row):
            if pd.isna(row['fecha_inicio']) or row['activo'] == 0: 
                return "Libre", "LIBRE HOY"
            try:
                f_ini = pd.to_datetime(row['fecha_inicio']).date()
                f_fin = pd.to_datetime(row['fecha_fin']).date() if not pd.isna(row['fecha_fin']) else f_ini + timedelta(days=30)
                
                if hoy < f_ini: return "RESERVADO", f_ini.strftime('%d/%m/%Y')
                elif hoy <= f_fin: return "OCUPADO", f_fin.strftime('%d/%m/%Y')
                else: return "VENCIDO", "LIBRE HOY"
            except: return "Libre", "LIBRE HOY"

        if not df.empty:
            df[['Situación', 'Disponible Desde']] = df.apply(lambda x: pd.Series(calcular_estado_visual(x)), axis=1)
            df['Alquiler'] = df['precio_alquiler'].apply(fmt_moneda)
            
            def color_semaforo(val):
                if val == "Libre": color = '#28a745' # Verde
                elif val == "OCUPADO": color = '#dc3545' # Rojo
                elif val == "RESERVADO": color = '#007bff' # Azul
                else: color = '#fd7e14' # Naranja
                return f'color: {color}; font-weight: bold'

            st.dataframe(
                df[["Bloque", "Unidad", "Situación", "Disponible Desde", "Alquiler"]].style.applymap(color_semaforo, subset=['Situación']), 
                use_container_width=True, hide_index=True
            )
        else:
            st.info("No hay datos. Cargue en Configuración.")
    except:
        st.error("Error de estructura. Pulse 'REINICIALIZAR TODO' en el menú.")

# ---------------------------------------------------------
# 2. NUEVO CONTRATO (CÁLCULO AUTOMÁTICO VENCIMIENTO)
# ---------------------------------------------------------
elif menu == "📝 Nuevo Contrato":
    st.subheader("Alta de Alquiler")
    conn = conectar()
    inm_db = pd.read_sql_query("SELECT id, tipo, precio_alquiler, costo_contrato, deposito_base FROM inmuebles", conn)
    inq_db = pd.read_sql_query("SELECT id, nombre FROM inquilinos", conn)
    
    if not inm_db.empty and not inq_db.empty:
        with st.form("form_contrato"):
            c1, c2 = st.columns(2)
            id_inm = c1.selectbox("Unidad", inm_db['id'].tolist(), format_func=lambda x: f"{x} - {inm_db[inm_db['id']==x]['tipo'].values[0]}")
            id_inq = c2.selectbox("Inquilino", inq_db['id'].tolist(), format_func=lambda x: inq_db[inq_db['id']==x]['nombre'].values[0])
            
            f_ini = c1.date_input("Fecha Inicio", date.today())
            meses = c2.number_input("Meses de Duración", min_value=1, value=6)
            f_fin = f_ini + timedelta(days=meses * 30)
            
            st.info(f"📅 Fecha Fin de Contrato: {f_fin.strftime('%d/%m/%Y')}")
            
            val_inm = inm_db[inm_db['id']==id_inm]
            m_alq = c1.number_input("Monto Alquiler", value=float(val_inm['precio_alquiler'].values[0]))
            m_con = c2.number_input("Costo Contrato", value=float(val_inm['costo_contrato'].values[0]))
            m_dep = c1.number_input("Depósito", value=float(val_inm['deposito_base'].values[0]))
            
            if st.form_submit_button("GRABAR CONTRATO"):
                cur = conn.cursor()
                cur.execute("""
                    INSERT INTO contratos (id_inmueble, id_inquilino, fecha_inicio, fecha_fin, meses, activo, monto_alquiler, monto_contrato, monto_deposito)
                    VALUES (?,?,?,?,?,1,?,?,?)
                """, (id_inm, id_inq, f_ini, f_fin, meses, m_alq, m_con, m_dep))
                conn.commit()
                st.success("Contrato guardado.")
                st.rerun()
    else:
        st.warning("Debe cargar Inmuebles e Inquilinos primero.")

# ---------------------------------------------------------
# 3. COBRANZAS (RECIBO WHATSAPP CON SALDO)
# ---------------------------------------------------------
elif menu == "💰 Cobranzas":
    st.subheader("Gestión de Cobros")
    conn = conectar()
    query_c = """
        SELECT d.id, i.tipo, inq.nombre, inq.celular, d.concepto, d.monto_debe, d.monto_pago
        FROM deudas d JOIN contratos c ON d.id_contrato=c.id
        JOIN inmuebles i ON c.id_inmueble=i.id JOIN inquilinos inq ON c.id_inquilino=inq.id
        WHERE d.pagado = 0
    """
    df_c = pd.read_sql_query(query_c, conn)
    
    if not df_c.empty:
        for _, row in df_c.iterrows():
            with st.expander(f"📌 {row['tipo']} - {row['nombre']} ({row['concepto']})"):
                saldo = float(row['monto_debe']) - float(row['monto_pago'])
                st.write(f"Pendiente: **{fmt_moneda(saldo)}**")
                pago_entregado = st.number_input(f"Monto a cobrar", min_value=0.0, max_value=saldo, key=f"p_{row['id']}")
                
                if st.button("Confirmar Pago", key=f"btn_{row['id']}"):
                    cur = conn.cursor()
                    nuevo_p = float(row['monto_pago']) + pago_entregado
                    es_p = 1 if nuevo_p >= float(row['monto_debe']) else 0
                    cur.execute("UPDATE deudas SET monto_pago=?, pagado=?, fecha_cobro=? WHERE id=?", 
                                (nuevo_p, es_p, date.today(), row['id']))
                    conn.commit()
                    
                    # Link WhatsApp
                    msg = f"✅ *RECIBO*\\nUnidad: {row['tipo']}\\nAbonado: {fmt_moneda(pago_entregado)}\\nSaldo restante: {fmt_moneda(saldo - pago_entregado)}"
                    st.session_state[f'wa_{row["id"]}'] = crear_link_whatsapp(row['celular'], msg)
                    st.rerun()
                
                if f'wa_{row["id"]}' in st.session_state:
                    st.markdown(f'<a href="{st.session_state[f"wa_{row[id]}"]}" target="_blank"><button style="background-color:#25D366; color:white; border:none; padding:10px; border-radius:5px; width:100%; cursor:pointer;">📲 WhatsApp</button></a>', unsafe_allow_html=True)
    else:
        st.info("Sin cobros pendientes.")

# ---------------------------------------------------------
# 4. MOROSOS (FILTRADO POR DEUDA REAL)
# ---------------------------------------------------------
elif menu == "🚨 Morosos":
    st.subheader("Inquilinos con Deuda")
    conn = conectar()
    df_m = pd.read_sql_query("""
        SELECT inq.nombre as Inquilino, i.tipo as Unidad, d.concepto as Concepto, (d.monto_debe - d.monto_pago) as Saldo
        FROM deudas d JOIN contratos c ON d.id_contrato=c.id
        JOIN inmuebles i ON c.id_inmueble=i.id JOIN inquilinos inq ON c.id_inquilino=inq.id
        WHERE d.pagado = 0 ORDER BY Saldo DESC
    """, conn)
    
    if not df_m.empty:
        st.error(f"Total en Mora: {fmt_moneda(df_m['Saldo'].sum())}")
        df_m['Saldo'] = df_m['Saldo'].apply(fmt_moneda)
        st.dataframe(df_m, use_container_width=True, hide_index=True)
        
        output = io.BytesIO()
        df_m.to_excel(output, index=False, engine='openpyxl')
        st.download_button("📊 Excel de Morosos", output.getvalue(), "morosos.xlsx")
    else:
        st.success("Cuentas al día.")

# ---------------------------------------------------------
# 5. CONFIGURACIÓN (RESTAURADO COMPLETO)
# ---------------------------------------------------------
elif menu == "⚙️ Configuración":
    st.subheader("Carga de Datos Maestros")
    tab1, tab2, tab3, tab4 = st.tabs(["👤 Inquilinos", "🏢 Bloques", "🏠 Unidades", "⚡ Procesos"])
    
    with tab1:
        with st.form("f_inquilino"):
            c1, c2 = st.columns(2)
            nombre = c1.text_input("Nombre Completo")
            celular = c2.text_input("Celular (549...)")
            procedencia = c1.text_input("Procedencia")
            grupo = c2.selectbox("Grupo", ["Solo/a", "Pareja", "Familia"])
            if st.form_submit_button("Guardar"):
                conn = conectar()
                conn.execute("INSERT INTO inquilinos (nombre, celular, procedencia, grupo) VALUES (?,?,?,?)", (nombre, celular, procedencia, grupo))
                conn.commit(); st.success("Inquilino guardado.")

    with tab2:
        with st.form("f_bloque"):
            nombre_b = st.text_input("Nombre del Bloque")
            if st.form_submit_button("Guardar"):
                conn = conectar(); conn.execute("INSERT INTO bloques (nombre) VALUES (?)", (nombre_b,))
                conn.commit(); st.success("Bloque guardado.")

    with tab3:
        with st.form("f_unidad"):
            conn = conectar(); blqs = pd.read_sql_query("SELECT * FROM bloques", conn)
            id_b = st.selectbox("Bloque", blqs['id'].tolist(), format_func=lambda x: blqs[blqs['id']==x]['nombre'].values[0]) if not blqs.empty else None
            tipo = st.text_input("Nombre de Unidad (Ej: Depto 1)")
            alquiler = st.number_input("Precio Alquiler Base", value=0.0)
            costo = st.number_input("Costo Contrato", value=0.0)
            deposito = st.number_input("Depósito Base", value=0.0)
            if st.form_submit_button("Guardar"):
                conn.execute("INSERT INTO inmuebles (id_bloque, tipo, precio_alquiler, costo_contrato, deposito_base) VALUES (?,?,?,?,?)", (id_b, tipo, alquiler, costo, deposito))
                conn.commit(); st.success("Unidad guardada.")

    with tab4:
        st.write("### Generación de Cuotas")
        mes_anio = st.text_input("Mes/Año (Ej: Junio 2025)")
        if st.button("🚀 Generar Alquileres de Mes"):
            conn = conectar()
            activos = pd.read_sql_query("SELECT id, monto_alquiler FROM contratos WHERE activo=1", conn)
            for _, c in activos.iterrows():
                conn.execute("INSERT INTO deudas (id_contrato, concepto, mes_anio, monto_debe) VALUES (?,?,?,?)",
                             (c['id'], "Alquiler", mes_anio, c['monto_alquiler']))
            conn.commit(); st.success(f"Cuotas de {mes_anio} generadas.")

# ---------------------------------------------------------
# 6. CAJA
# ---------------------------------------------------------
elif menu == "📊 Caja":
    st.subheader("Ingresos Recaudados")
    df_caja = pd.read_sql_query("SELECT fecha_cobro as Fecha, concepto as Detalle, monto_pago as Monto FROM deudas WHERE pagado = 1", conectar())
    if not df_caja.empty:
        st.metric("Recaudación Total", fmt_moneda(df_caja['Monto'].sum()))
        df_caja['Monto'] = df_caja['Monto'].apply(fmt_moneda)
        st.table(df_caja)
