import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, date, timedelta
import io
import urllib.parse

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(
    page_title="Inmobiliaria Pro Cloud", 
    layout="wide", 
    initial_sidebar_state="expanded"
)

# --- FUNCIONES DE APOYO Y FORMATEO ---
def conectar():
    return sqlite3.connect('datos_alquileres.db', check_same_thread=False)

def fmt_moneda(valor):
    """Formatea a moneda sin decimales y con punto en miles: $ 1.250.000"""
    try:
        return f"$ {int(float(valor)):,}".replace(",", ".")
    except:
        return "$ 0"

def crear_link_whatsapp(tel, mensaje):
    """Genera link de WhatsApp API"""
    texto = urllib.parse.quote(mensaje)
    return f"https://api.whatsapp.com/send?phone={tel}&text={texto}"

def init_db():
    conn = conectar()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS bloques (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT UNIQUE)''')
    c.execute('''CREATE TABLE IF NOT EXISTS inmuebles (id INTEGER PRIMARY KEY AUTOINCREMENT, id_bloque INTEGER, tipo TEXT, precio_alquiler REAL, costo_contrato REAL, deposito_base REAL, estado TEXT DEFAULT 'Libre')''')
    c.execute('''CREATE TABLE IF NOT EXISTS inquilinos (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT, celular TEXT, procedencia TEXT, grupo TEXT, em_nombre TEXT, em_tel TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS contratos (id INTEGER PRIMARY KEY AUTOINCREMENT, id_inmueble INTEGER, id_inquilino INTEGER, fecha_inicio DATE, meses INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS deudas (id INTEGER PRIMARY KEY AUTOINCREMENT, id_contrato INTEGER, concepto TEXT, mes_anio TEXT, monto_debe REAL, monto_pago REAL DEFAULT 0, pagado INTEGER DEFAULT 0, fecha_cobro DATE)''')

    # MIGRACIÓN AUTOMÁTICA DE COLUMNAS
    columnas_contratos = [
        ("fecha_fin", "DATE"), ("activo", "INTEGER DEFAULT 1"),
        ("monto_alquiler", "REAL DEFAULT 0"), ("monto_contrato", "REAL DEFAULT 0"),
        ("monto_deposito", "REAL DEFAULT 0")
    ]
    for col, tipo in columnas_contratos:
        try: c.execute(f"ALTER TABLE contratos ADD COLUMN {col} {tipo}")
        except: pass 
    conn.commit()
    conn.close()

init_db()

# --- MENÚ LATERAL VISUAL ---
with st.sidebar:
    st.title("🏢 Inmobiliaria Pro")
    st.divider()
    menu = st.radio("Navegación:", ["🏠 Inventario", "📝 Nuevo Contrato", "💰 Cobranzas", "🚨 Morosos", "📊 Caja"], label_visibility="collapsed")
    st.divider()
    conn_s = conectar()
    res = conn_s.execute("SELECT COUNT(*) FROM inmuebles").fetchone()
    st.write(f"**Total Unidades:** {res[0]}")
    conn_s.close()

# ---------------------------------------------------------
# 1. INVENTARIO PREDICTIVO
# ---------------------------------------------------------
if menu == "🏠 Inventario":
    st.subheader("Estado de Unidades y Disponibilidad")
    conn = conectar()
    hoy = date.today()
    f1, f2, f3 = st.columns([2, 2, 2])
    filtro_sit = f1.selectbox("Situación Actual", ["TODOS", "Libres Ahora", "Ocupados Ahora"])
    bloques_db = pd.read_sql_query("SELECT nombre FROM bloques", conn)
    filtro_blq = f2.selectbox("Filtrar Bloque", ["TODOS"] + bloques_db['nombre'].tolist())
    busqueda = f3.text_input("Buscar Unidad...")

    query = """
        SELECT i.id, b.nombre as Bloque, i.tipo as Unidad, i.precio_alquiler,
               c.fecha_inicio, c.fecha_fin, c.activo
        FROM inmuebles i
        JOIN bloques b ON i.id_bloque = b.id
        LEFT JOIN contratos c ON i.id = c.id_inmueble AND c.activo = 1
    """
    df = pd.read_sql_query(query, conn)

    def calcular_estado(row):
        if pd.isna(row['fecha_inicio']) or row['activo'] == 0: return "Libre", "INMEDIATA"
        try:
            f_ini = pd.to_datetime(row['fecha_inicio']).date()
            f_fin = pd.to_datetime(row['fecha_fin']).date()
            if hoy < f_ini: return "RESERVADO", f_ini.strftime('%d/%m/%Y')
            elif hoy <= f_fin: return "OCUPADO", f_fin.strftime('%d/%m/%Y')
            else: return "VENCIDO", "INMEDIATA"
        except: return "Libre", "INMEDIATA"

    df[['Estado', 'Disponible']] = df.apply(lambda x: pd.Series(calcular_estado(x)), axis=1)
    if filtro_sit == "Libres Ahora": df = df[df['Estado'].str.contains("Libre|VENCIDO")]
    elif filtro_sit == "Ocupados Ahora": df = df[df['Estado'] == "OCUPADO"]
    if filtro_blq != "TODOS": df = df[df['Bloque'] == filtro_blq]
    if busqueda: df = df[df['Unidad'].str.contains(busqueda, case=False)]

    df['Precio'] = df['precio_alquiler'].apply(fmt_moneda)
    st.dataframe(df[["Bloque", "Unidad", "Estado", "Disponible", "Precio"]], use_container_width=True, hide_index=True)

# ---------------------------------------------------------
# 3. COBRANZAS (CON RECIBO WHATSAPP)
# ---------------------------------------------------------
elif menu == "💰 Cobranzas":
    st.subheader("Gestión de Cobros")
    conn = conectar()
    query_c = """
        SELECT d.id, i.tipo as Unidad, inq.nombre as Inquilino, d.concepto, 
               d.monto_debe, d.monto_pago, inq.celular
        FROM deudas d
        JOIN contratos c ON d.id_contrato = c.id
        JOIN inmuebles i ON c.id_inmueble = i.id
        JOIN inquilinos inq ON c.id_inquilino = inq.id
        WHERE d.pagado = 0
    """
    df_c = pd.read_sql_query(query_c, conn)
    
    if not df_c.empty:
        for _, row in df_c.iterrows():
            with st.expander(f"📍 {row['Unidad']} - {row['Inquilino']} ({row['concepto']})"):
                saldo = float(row['monto_debe']) - float(row['monto_pago'])
                st.write(f"Saldo Pendiente: **{fmt_moneda(saldo)}**")
                p_monto = st.number_input(f"Monto a entregar", min_value=0.0, max_value=saldo, key=f"p_{row['id']}")
                
                if st.button(f"Confirmar Cobro ID {row['id']}"):
                    cur = conn.cursor()
                    nuevo_p = float(row['monto_pago']) + p_monto
                    estado_p = 1 if nuevo_p >= float(row['monto_debe']) else 0
                    cur.execute("UPDATE deudas SET monto_pago=?, pagado=?, fecha_cobro=? WHERE id=?", 
                                (nuevo_p, estado_p, date.today(), row['id']))
                    conn.commit()
                    
                    # --- LÓGICA DE WHATSAPP ---
                    msg = f"✅ *RECIBO DE PAGO*\n\n" \
                          f"Unidad: *{row['Unidad']}*\n" \
                          f"Inquilino: *{row['Inquilino']}*\n" \
                          f"Concepto: {row['concepto']}\n" \
                          f"Monto Abonado: *{fmt_moneda(p_monto)}*\n" \
                          f"Fecha: {date.today().strftime('%d/%m/%Y')}\n\n" \
                          f"¡Muchas gracias!"
                    
                    st.session_state[f'link_{row["id"]}'] = crear_link_whatsapp(row['celular'], msg)
                    st.success(f"Cobro registrado.")
                
                # Botón de WhatsApp persistente tras el pago
                if f'link_{row["id"]}' in st.session_state:
                    st.markdown(f"""
                        <a href="{st.session_state[f'link_{row["id"]}']}" target="_blank">
                            <button style="background-color:#25D366; color:white; border:none; padding:10px 20px; border-radius:5px; cursor:pointer; width:100%;">
                                📲 Enviar Recibo por WhatsApp
                            </button>
                        </a>
                    """, unsafe_allow_html=True)
    else:
        st.info("No hay deudas pendientes.")

# ---------------------------------------------------------
# 4. MOROSOS
# ---------------------------------------------------------
elif menu == "🚨 Morosos":
    st.subheader("Inquilinos con Deuda Pendiente")
    conn = conectar()
    query_m = """
        SELECT inq.nombre as Inquilino, i.tipo as Unidad, d.concepto as Concepto,
               (d.monto_debe - d.monto_pago) as Saldo_Mora, inq.celular as Contacto
        FROM deudas d
        JOIN contratos c ON d.id_contrato = c.id
        JOIN inmuebles i ON c.id_inmueble = i.id
        JOIN inquilinos inq ON c.id_inquilino = inq.id
        WHERE d.pagado = 0
        ORDER BY Saldo_Mora DESC
    """
    df_m = pd.read_sql_query(query_m, conn)
    if not df_m.empty:
        total_m = df_m['Saldo_Mora'].sum()
        st.error(f"### TOTAL EN MORA: {fmt_moneda(total_m)}")
        df_view = df_m.copy()
        df_view['Saldo_Mora'] = df_view['Saldo_Mora'].apply(fmt_moneda)
        st.dataframe(df_view, use_container_width=True, hide_index=True)
    else:
        st.success("No hay deudas pendientes.")

# ---------------------------------------------------------
# 5. CAJA
# ---------------------------------------------------------
elif menu == "📊 Caja":
    st.subheader("Resumen de Ingresos")
    conn = conectar()
    df_caja = pd.read_sql_query("SELECT fecha_cobro as Fecha, concepto as Detalle, monto_pago as Monto FROM deudas WHERE pagado = 1", conn)
    if not df_caja.empty:
        st.metric("Total Cobrado", fmt_moneda(df_caja['Monto'].sum()))
        df_caja['Monto'] = df_caja['Monto'].apply(fmt_moneda)
        st.table(df_caja)
