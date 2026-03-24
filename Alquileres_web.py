import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, date, timedelta
import io
import urllib.parse

# --- 1. CONFIGURACIÓN DE NAVEGACIÓN Y ESTILO ---
st.set_page_config(
    page_title="Inmobiliaria Pro Cloud", 
    layout="wide", 
    initial_sidebar_state="expanded"
)

# --- 2. FUNCIONES DE APOYO (EL MOTOR DEL SISTEMA) ---
def conectar():
    """Conexión segura a SQLite compatible con hilos de Streamlit"""
    return sqlite3.connect('datos_alquileres.db', check_same_thread=False)

def fmt_moneda(valor):
    """Formatea importes: $ 1.250.000 (sin decimales, con punto de miles)"""
    try:
        # Forzamos float y luego int para limpiar cualquier residuo de la DB
        return f"$ {int(float(valor)):,}".replace(",", ".")
    except:
        return "$ 0"

def crear_link_whatsapp(tel, mensaje):
    """Codifica el mensaje para que funcione como link directo a la App"""
    texto = urllib.parse.quote(mensaje)
    return f"https://api.whatsapp.com/send?phone={tel}&text={texto}"

# --- 3. INICIALIZACIÓN Y AUTO-MIGRACIÓN DE DB ---
def init_db():
    conn = conectar()
    c = conn.cursor()
    
    # Creamos las tablas base si no existen (Basado en tu original)
    c.execute('''CREATE TABLE IF NOT EXISTS bloques (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT UNIQUE)''')
    c.execute('''CREATE TABLE IF NOT EXISTS inmuebles (id INTEGER PRIMARY KEY AUTOINCREMENT, id_bloque INTEGER, tipo TEXT, precio_alquiler REAL, costo_contrato REAL, deposito_base REAL, estado TEXT DEFAULT 'Libre')''')
    c.execute('''CREATE TABLE IF NOT EXISTS inquilinos (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT, celular TEXT, procedencia TEXT, grupo TEXT, em_nombre TEXT, em_tel TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS contratos (id INTEGER PRIMARY KEY AUTOINCREMENT, id_inmueble INTEGER, id_inquilino INTEGER, fecha_inicio DATE, meses INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS deudas (id INTEGER PRIMARY KEY AUTOINCREMENT, id_contrato INTEGER, concepto TEXT, mes_anio TEXT, monto_debe REAL, monto_pago REAL DEFAULT 0, pagado INTEGER DEFAULT 0, fecha_cobro DATE)''')

    # MIGRACIÓN: Agregamos columnas predictivas y financieras si no existen
    # Esto evita el DatabaseError al ejecutar el sistema por primera vez
    columnas_contratos = [
        ("fecha_fin", "DATE"), 
        ("activo", "INTEGER DEFAULT 1"),
        ("monto_alquiler", "REAL DEFAULT 0"), 
        ("monto_contrato", "REAL DEFAULT 0"),
        ("monto_deposito", "REAL DEFAULT 0")
    ]
    for col, tipo in columnas_contratos:
        try:
            c.execute(f"ALTER TABLE contratos ADD COLUMN {col} {tipo}")
        except sqlite3.OperationalError:
            pass # La columna ya existe, no hacemos nada
            
    conn.commit()
    conn.close()

# Ejecutamos la inicialización al cargar el script
init_db()

# --- 4. MENÚ LATERAL VISUAL (ICONOS FIJOS) ---
with st.sidebar:
    st.title("🏢 Inmobiliaria Pro")
    st.divider()
    # Menú estático con iconos
    menu = st.radio(
        "Navegación:",
        ["🏠 Inventario", "📝 Nuevo Contrato", "💰 Cobranzas", "🚨 Morosos", "📊 Caja"],
        label_visibility="collapsed"
    )
    
    st.divider()
    # Widget de estado rápido en el lateral
    conn_s = conectar()
    try:
        total_inm = conn_s.execute("SELECT COUNT(*) FROM inmuebles").fetchone()[0]
        st.write(f"**Total Unidades:** {total_inm}")
    except:
        pass
    conn_s.close()

# ---------------------------------------------------------
# 1. MÓDULO: INVENTARIO PREDICTIVO (LÓGICA DE FECHAS)
# ---------------------------------------------------------
if menu == "🏠 Inventario":
    st.subheader("Estado de Unidades y Disponibilidad")
    conn = conectar()
    hoy = date.today()

    # Filtros superiores
    f1, f2, f3 = st.columns([2, 2, 2])
    filtro_sit = f1.selectbox("Situación Actual", ["TODOS", "Libres Ahora", "Ocupados Ahora"])
    
    bloques_db = pd.read_sql_query("SELECT nombre FROM bloques", conn)
    filtro_blq = f2.selectbox("Filtrar Bloque", ["TODOS"] + bloques_db['nombre'].tolist())
    busqueda = f3.text_input("Buscar Unidad (Tipo o ID)...")

    # Query Maestra: Cruce de inmuebles con sus contratos activos
    query_inv = """
        SELECT 
            i.id, 
            b.nombre as Bloque, 
            i.tipo as Unidad, 
            i.precio_alquiler,
            c.fecha_inicio, 
            c.fecha_fin, 
            c.activo
        FROM inmuebles i
        JOIN bloques b ON i.id_bloque = b.id
        LEFT JOIN contratos c ON i.id = c.id_inmueble AND c.activo = 1
    """
    df = pd.read_sql_query(query_inv, conn)

    # LÓGICA PREDICTIVA: Determinamos el estado real por fecha
    def calcular_estado_real(row):
        # Si no hay contrato o está inactivo -> Libre
        if pd.isna(row['fecha_inicio']) or row['activo'] == 0:
            return "Libre", "INMEDIATA"
        
        try:
            # Convertimos strings de DB a objetos date de Python para comparar
            f_ini = pd.to_datetime(row['fecha_inicio']).date()
            f_fin = pd.to_datetime(row['fecha_fin']).date()
            
            if hoy < f_ini:
                return "RESERVADO", f_ini.strftime('%d/%m/%Y')
            elif hoy <= f_fin:
                return "OCUPADO", f_fin.strftime('%d/%m/%Y')
            else:
                # El contrato terminó pero sigue figurando activo en DB
                return "CONTRATO VENCIDO", "INMEDIATA"
        except:
            return "Libre", "INMEDIATA"

    # Aplicamos la lógica y creamos las columnas calculadas
    df[['Estado', 'Disponible Desde']] = df.apply(lambda x: pd.Series(calcular_estado_real(x)), axis=1)
    
    # Aplicación de los filtros del usuario
    if filtro_sit == "Libres Ahora":
        df = df[df['Estado'].str.contains("Libre|VENCIDO")]
    elif filtro_sit == "Ocupados Ahora":
        df = df[df['Estado'] == "OCUPADO"]
        
    if filtro_blq != "TODOS":
        df = df[df['Bloque'] == filtro_blq]
        
    if busqueda:
        df = df[df['Unidad'].str.contains(busqueda, case=False)]

    # Formateo de precios (usando nuestra función de la Parte 1)
    df['Alquiler'] = df['precio_alquiler'].apply(fmt_moneda)

    # Configuración de colores para la tabla
    def color_sit(val):
        if "Libre" in val: color = '#2ecc71' # Verde
        elif val == "OCUPADO": color = '#e74c3c' # Rojo
        elif val == "RESERVADO": color = '#3498db' # Azul
        else: color = '#f39c12' # Naranja (Vencidos)
        return f'color: {color}; font-weight: bold'

    # Mostrar tabla final
    cols_finales = ["Bloque", "Unidad", "Estado", "Disponible Desde", "Alquiler"]
    st.dataframe(
        df[cols_finales].style.applymap(color_sit, subset=['Estado']),
        use_container_width=True, 
        hide_index=True
    )
