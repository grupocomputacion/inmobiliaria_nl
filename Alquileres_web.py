import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, date, timedelta
import io

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
        return f"$ {int(valor):,}".replace(",", ".")
    except:
        return "$ 0"

def init_db():
    conn = conectar()
    c = conn.cursor()
    # Estructura normalizada con fecha_fin para predictibilidad
    c.executescript('''
        CREATE TABLE IF NOT EXISTS bloques (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            nombre TEXT UNIQUE
        );
        CREATE TABLE IF NOT EXISTS inmuebles (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            id_bloque INTEGER, 
            tipo TEXT, 
            precio_alquiler REAL, 
            costo_contrato REAL, 
            deposito_base REAL, 
            estado TEXT DEFAULT 'Libre'
        );
        CREATE TABLE IF NOT EXISTS inquilinos (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            nombre TEXT, 
            celular TEXT, 
            procedencia TEXT, 
            grupo TEXT, 
            em_nombre TEXT, 
            em_tel TEXT
        );
        CREATE TABLE IF NOT EXISTS contratos (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            id_inmueble INTEGER, 
            id_inquilino INTEGER, 
            fecha_inicio DATE, 
            fecha_fin DATE, 
            meses INTEGER, 
            activo INTEGER DEFAULT 1, 
            monto_alquiler REAL, 
            monto_contrato REAL, 
            monto_deposito REAL
        );
        CREATE TABLE IF NOT EXISTS deudas (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            id_contrato INTEGER, 
            concepto TEXT, 
            mes_anio TEXT, 
            monto_debe REAL, 
            monto_pago REAL DEFAULT 0, 
            pagado INTEGER DEFAULT 0, 
            fecha_cobro DATE
        );
    ''')
    conn.commit()
    conn.close()

init_db()

# --- MENÚ LATERAL VISUAL (ICONOS FIJOS) ---
with st.sidebar:
    st.title("🏢 Inmobiliaria Pro")
    st.divider()
    menu = st.radio(
        "Navegación:",
        ["🏠 Inventario", "📝 Nuevo Contrato", "💰 Cobranzas", "🚨 Morosos", "📊 Caja"],
        label_visibility="collapsed"
    )
    
    # Widget de resumen rápido en el menú
    st.divider()
    conn_s = conectar()
    total_inm = pd.read_sql_query("SELECT COUNT(*) as total FROM inmuebles", conn_s).iloc[0]['total']
    st.write(f"**Total Unidades:** {total_inm}")
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
        if pd.isna(row['fecha_inicio']) or row['activo'] == 0:
            return "Libre", "INMEDIATA"
        try:
            f_ini = datetime.strptime(str(row['fecha_inicio']), '%Y-%m-%d').date()
            f_fin = datetime.strptime(str(row['fecha_fin']), '%Y-%m-%d').date()
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

    def color_sit(val):
        color = '#2ecc71' if "Libre" in val else '#e74c3c' if val == "OCUPADO" else '#3498db'
        return f'color: {color}; font-weight: bold'

    st.dataframe(df[["Bloque", "Unidad", "Estado", "Disponible", "Precio"]].style.applymap(color_sit, subset=['Estado']),
                 use_container_width=True, hide_index=True)

# ---------------------------------------------------------
# 2. NUEVO CONTRATO
# ---------------------------------------------------------
elif menu == "📝 Nuevo Contrato":
    st.subheader("Carga de Nuevo Contrato")
    conn = conectar()
    inm_db = pd.read_sql_query("SELECT id, tipo FROM inmuebles", conn)
    inq_db = pd.read_sql_query("SELECT id, nombre FROM inquilinos", conn)

    with st.form("form_c"):
        c1, c2 = st.columns(2)
        inm_id = c1.selectbox("Unidad", inm_db['id'].tolist(), format_func=lambda x: f"ID {x} - {inm_db[inm_db['id']==x]['tipo'].values[0]}")
        inq_id = c2.selectbox("Inquilino", inq_db['id'].tolist(), format_func=lambda x: inq_db[inq_db['id']==x]['nombre'].values[0])
        
        f_ini = c1.date_input("Fecha Inicio", date.today())
        meses = c2.number_input("Duración (Meses)", min_value=1, value=6)
        
        # Fecha fin calculada
        f_fin = f_ini + timedelta(days=meses * 30)
        st.info(f"📅 Fin de Contrato: {f_fin.strftime('%d/%m/%Y')}")

        m_alq = c1.number_input("Monto Alquiler ($)", value=0.0)
        if st.form_submit_button("GRABAR"):
            cur = conn.cursor()
            cur.execute("INSERT INTO contratos (id_inmueble, id_inquilino, fecha_inicio, fecha_fin, meses, monto_alquiler) VALUES (?,?,?,?,?,?)",
                        (inm_id, inq_id, f_ini, f_fin, meses, m_alq))
            conn.commit()
            st.success("Contrato guardado correctamente.")
            st.rerun()

# ---------------------------------------------------------
# 3. COBRANZAS
# ---------------------------------------------------------
elif menu == "💰 Cobranzas":
    st.subheader("Gestión de Cobros")
    conn = conectar()
    query_c = """
        SELECT d.id, i.tipo, inq.nombre, d.concepto, d.monto_debe, d.monto_pago
        FROM deudas d
        JOIN contratos c ON d.id_contrato = c.id
        JOIN inmuebles i ON c.id_inmueble = i.id
        JOIN inquilinos inq ON c.id_inquilino = inq.id
        WHERE d.pagado = 0
    """
    df_c = pd.read_sql_query(query_c, conn)
    
    for _, row in df_c.iterrows():
        with st.expander(f"{row['tipo']} - {row['nombre']} ({row['concepto']})"):
            saldo = row['monto_debe'] - row['monto_pago']
            st.write(f"Deuda: **{fmt_moneda(saldo)}**")
            p_monto = st.number_input(f"Monto a pagar", min_value=0.0, max_value=float(saldo), key=f"p_{row['id']}")
            if st.button(f"Confirmar Pago {row['id']}"):
                cur = conn.cursor()
                nuevo_p = row['monto_pago'] + p_monto
                estado_p = 1 if nuevo_p >= row['monto_debe'] else 0
                cur.execute("UPDATE deudas SET monto_pago=?, pagado=?, fecha_cobro=? WHERE id=?", 
                            (nuevo_p, estado_p, date.today(), row['id']))
                conn.commit(); st.rerun()

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
        
        output = io.BytesIO()
        df_m.to_excel(output, index=False, engine='openpyxl')
        st.download_button("📊 Descargar Morosos (Excel)", output.getvalue(), f"morosos_{date.today()}.xlsx")
    else:
        st.success("No hay deudas pendientes registradas.")

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
