import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, date, timedelta
import os

# ==========================================
# 1. CONFIGURACIÓN E IDENTIDAD VISUAL
# ==========================================
st.set_page_config(page_title="NL Propiedades - Gestión", page_icon="🏠", layout="wide")

# CONTROL DE ENTORNO: Cambiar a True para ocultar el botón de Reset
ES_PRODUCCION = False 

# Estilo Dorado y Negro
st.markdown("""
    <style>
    .stButton>button { background-color: #D4AF37; color: black; border-radius: 5px; font-weight: bold; }
    .stButton>button:hover { background-color: #B8860B; color: white; }
    h1, h2, h3 { color: #D4AF37; }
    </style>
    """, unsafe_allow_html=True)

def conectar():
    return sqlite3.connect('datos_alquileres.db', check_same_thread=False, timeout=20)

def fmt_moneda(valor):
    try: return f"$ {int(float(valor or 0)):,}".replace(",", ".")
    except: return "$ 0"

def limpiar_monto(texto):
    if not texto: return 0
    try: return int(float(str(texto).replace('$', '').replace('.', '').replace(',', '').strip()))
    except: return 0

def inicializar_db():
    conn = conectar()
    c = conn.cursor()
    c.executescript('''
        CREATE TABLE IF NOT EXISTS bloques (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT UNIQUE);
        CREATE TABLE IF NOT EXISTS inmuebles (
            id INTEGER PRIMARY KEY AUTOINCREMENT, id_bloque INTEGER, tipo TEXT, 
            precio_alquiler INTEGER, costo_contrato INTEGER, deposito_base INTEGER, UNIQUE(id_bloque, tipo)
        );
        CREATE TABLE IF NOT EXISTS inquilinos (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT);
        CREATE TABLE IF NOT EXISTS contratos (
            id INTEGER PRIMARY KEY AUTOINCREMENT, id_inmueble INTEGER, id_inquilino INTEGER, 
            fecha_inicio DATE, fecha_fin DATE, meses INTEGER, activo INTEGER DEFAULT 1, 
            monto_alquiler INTEGER, monto_contrato INTEGER, monto_deposito INTEGER
        );
        CREATE TABLE IF NOT EXISTS deudas (
            id INTEGER PRIMARY KEY AUTOINCREMENT, id_contrato INTEGER, concepto TEXT, 
            mes_anio TEXT, monto_debe INTEGER, monto_pago INTEGER DEFAULT 0, pagado INTEGER DEFAULT 0, fecha_cobro DATE
        );
    ''')
    
    # Migración de columnas para evitar errores de consulta
    columnas_inq = [('celular','TEXT'), ('dni','TEXT'), ('direccion','TEXT'), ('emergencia_contacto','TEXT'), ('procedencia','TEXT'), ('grupo','TEXT')]
    for col, tipo in columnas_inq:
        try: c.execute(f"ALTER TABLE inquilinos ADD COLUMN {col} {tipo}")
        except: pass
    conn.commit()
    conn.close()

inicializar_db()

# ==========================================
# 2. MENÚ LATERAL
# ==========================================
with st.sidebar:
    try: st.image("logo.jpg", use_container_width=True)
    except: st.title("NL PROPIEDADES")
    st.divider()
    menu = st.radio("Navegación:", ["🏠 1. Inventario", "📝 2. Nuevo Contrato", "💰 3. Cobranzas", "🚨 4. Morosos", "📊 5. Caja", "⚙️ 6. Maestros"])
    
    # LÓGICA DE SEGURIDAD PARA EL BOTÓN DE RESET
    if not ES_PRODUCCION:
        st.divider()
        st.warning("MODO DESARROLLO")
        if st.button("🚨 REINICIAR TODO"):
            if os.path.exists('datos_alquileres.db'): os.remove('datos_alquileres.db')
            inicializar_db()
            st.rerun()

# ==========================================
# 🏠 1. INVENTARIO (SIN DUPLICADOS)
# ==========================================
if menu == "🏠 1. Inventario":
    st.header("Estado de Unidades")
    conn = conectar()
    query = """
        SELECT i.id, b.nombre as Bloque, i.tipo as Unidad, 
               i.precio_alquiler, i.costo_contrato, i.deposito_base,
               MAX(c.fecha_fin) as Fin, MAX(c.activo) as ocupado
        FROM inmuebles i
        JOIN bloques b ON i.id_bloque = b.id
        LEFT JOIN contratos c ON i.id = c.id_inmueble AND c.activo = 1
        GROUP BY i.id
    """
    df = pd.read_sql_query(query, conn)
    conn.close()

    if not df.empty:
        df['Situación'] = df['ocupado'].apply(lambda x: "🔴 OCUPADO" if x == 1 else "🟢 LIBRE")
        df['Precio'] = df['precio_alquiler'].apply(fmt_moneda)
        st.dataframe(df[["Bloque", "Unidad", "Situación", "Fin", "Precio"]], use_container_width=True, hide_index=True)
    else: st.info("Sin unidades cargadas.")

# ==========================================
# 📝 2. NUEVO CONTRATO (CON AUTO-DEUDAS)
# ==========================================
elif menu == "📝 2. Nuevo Contrato":
    st.header("Alta de Contrato")
    conn = conectar()
    inm = pd.read_sql_query("SELECT i.id, b.nombre || ' - ' || i.tipo as ref, i.precio_alquiler, i.costo_contrato, i.deposito_base FROM inmuebles i JOIN bloques b ON i.id_bloque=b.id", conn)
    inq = pd.read_sql_query("SELECT id, nombre FROM inquilinos", conn)
    
    if not inm.empty and not inq.empty:
        with st.form("f_contrato", clear_on_submit=True):
            c1, c2 = st.columns(2)
            id_u = c1.selectbox("Unidad", inm['id'].tolist(), format_func=lambda x: inm[inm['id']==x]['ref'].values[0])
            id_i = c2.selectbox("Inquilino", inq['id'].tolist(), format_func=lambda x: inq[inq['id']==x]['nombre'].values[0])
            f_ini = c1.date_input("Inicio", date.today())
            meses = c2.number_input("Meses", 1, 60, 6)
            
            u_data = inm[inm['id']==id_u].iloc[0]
            m_alq = c1.text_input("Alquiler", value=str(int(u_data['precio_alquiler'])))
            m_con = c2.text_input("Contrato", value=str(int(u_data['costo_contrato'])))
            m_dep = c1.text_input("Depósito", value=str(int(u_data['deposito_base'])))
            
            if st.form_submit_button("GRABAR Y GENERAR COBROS"):
                f_fin = f_ini + timedelta(days=meses*30)
                cur = conn.cursor()
                cur.execute("INSERT INTO contratos (id_inmueble, id_inquilino, fecha_inicio, fecha_fin, meses, monto_alquiler, monto_contrato, monto_deposito) VALUES (?,?,?,?,?,?,?,?)",
                            (id_u, id_i, f_ini, f_fin, meses, limpiar_monto(m_alq), limpiar_monto(m_con), limpiar_monto(m_dep)))
                id_c = cur.lastrowid
                
                mes_txt = f_ini.strftime("%m/%Y")
                cur.executemany("INSERT INTO deudas (id_contrato, concepto, mes_anio, monto_debe) VALUES (?,?,?,?)", [
                    (id_c, "Contrato", mes_txt, limpiar_monto(m_con)),
                    (id_c, "Depósito", mes_txt, limpiar_monto(m_dep)),
                    (id_c, "Mes 1", mes_txt, limpiar_monto(m_alq))
                ])
                conn.commit(); st.success("¡Contrato y deudas iniciales generadas!"); st.rerun()
    conn.close()

# ==========================================
# ⚙️ 6. MAESTROS (VER CONTRATOS INTEGRADO)
# ==========================================
elif menu == "⚙️ 6. Maestros":
    st.header("Maestros")
    t1, t2, t3, t4 = st.tabs(["👤 Inquilinos", "🏢 Bloques", "🏠 Unidades", "📋 Ver Contratos"])
    
    with t1:
        con = conectar()
        with st.form("f_inq", clear_on_submit=True):
            ca, cb = st.columns(2)
            n, d = ca.text_input("Nombre"), cb.text_input("DNI")
            c, p = ca.text_input("WhatsApp"), cb.text_input("Procedencia")
            if st.form_submit_button("Guardar"):
                con.execute("INSERT INTO inquilinos (nombre, dni, celular, procedencia) VALUES (?,?,?,?)", (n, d, c, p))
                con.commit(); st.rerun()
        st.write("---")
        df_inq = pd.read_sql_query("SELECT nombre, dni, celular, procedencia FROM inquilinos", con)
        st.table(df_inq)
        con.close()

    with t4:
        st.write("### Listado de Contratos")
        con = conectar()
        df_ver = pd.read_sql_query("""
            SELECT c.id, inq.nombre as Inquilino, i.tipo as Unidad, c.fecha_inicio, c.fecha_fin, c.activo
            FROM contratos c 
            JOIN inquilinos inq ON c.id_inquilino = inq.id
            JOIN inmuebles i ON c.id_inmueble = i.id
        """, con)
        st.dataframe(df_ver, use_container_width=True, hide_index=True)
        con.close()
