import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, date, timedelta
import os

# ==========================================
# 1. CONFIGURACIÓN E IDENTIDAD VISUAL
# ==========================================
st.set_page_config(page_title="NL Propiedades - Gestión", page_icon="🏠", layout="wide")

# Switch de seguridad para el botón de Reset
ES_PRODUCCION = False 

st.markdown("""
    <style>
    .stButton>button { background-color: #D4AF37; color: black; border-radius: 5px; font-weight: bold; width: 100%; }
    .stButton>button:hover { background-color: #B8860B; color: white; }
    h1, h2, h3, h4 { color: #D4AF37; }
    .stTabs [data-baseweb="tab-list"] { gap: 10px; }
    .stTabs [data-baseweb="tab"] { background-color: #f0f2f6; border-radius: 5px; padding: 10px; }
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 2. FUNCIONES DE BASE DE DATOS
# ==========================================
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
        CREATE TABLE IF NOT EXISTS inquilinos (
            id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT, celular TEXT, dni TEXT, 
            direccion TEXT, emergencia_contacto TEXT, procedencia TEXT, grupo TEXT
        );
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
    conn.commit()
    conn.close()

inicializar_db()

# ==========================================
# 3. BARRA LATERAL
# ==========================================
with st.sidebar:
    try: st.image("logo.jpg", use_container_width=True)
    except: st.title("NL PROPIEDADES")
    
    st.divider()
    menu = st.radio("Navegación:", ["🏠 1. Inventario", "📝 2. Nuevo Contrato", "💰 3. Cobranzas", "🚨 4. Morosos", "📊 5. Caja", "⚙️ 6. Maestros"])
    
    if not ES_PRODUCCION:
        st.divider()
        st.caption("Herramientas de Desarrollador")
        if st.button("🚨 REINICIAR BASE DE DATOS"):
            if os.path.exists('datos_alquileres.db'): os.remove('datos_alquileres.db')
            inicializar_db()
            st.rerun()

# ==========================================
# 4. SECCIONES PRINCIPALES
# ==========================================

if menu == "🏠 1. Inventario":
    st.header("Estado de Unidades")
    conn = conectar()
    query = """
        SELECT b.nombre as Bloque, i.tipo as Unidad, i.precio_alquiler,
               MAX(c.fecha_fin) as Vence, MAX(c.activo) as ocupado
        FROM inmuebles i
        JOIN bloques b ON i.id_bloque = b.id
        LEFT JOIN contratos c ON i.id = c.id_inmueble AND c.activo = 1
        GROUP BY i.id
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    if not df.empty:
        df['Situación'] = df['ocupado'].apply(lambda x: "🔴 OCUPADO" if x == 1 else "🟢 LIBRE")
        df['Alquiler'] = df['precio_alquiler'].apply(fmt_moneda)
        st.dataframe(df[["Bloque", "Unidad", "Situación", "Vence", "Alquiler"]], use_container_width=True, hide_index=True)
    else: st.info("Cargue datos en la sección de Maestros.")

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
            f_ini = c1.date_input("Fecha Inicio", date.today())
            meses = c2.number_input("Duración (Meses)", 1, 60, 6)
            
            u_data = inm[inm['id']==id_u].iloc[0]
            m_alq = c1.text_input("Monto Alquiler", value=str(int(u_data['precio_alquiler'])))
            m_con = c2.text_input("Monto Contrato", value=str(int(u_data['costo_contrato'])))
            m_dep = c1.text_input("Monto Depósito", value=str(int(u_data['deposito_base'])))
            
            if st.form_submit_button("GRABAR CONTRATO Y DEUDAS"):
                f_fin = f_ini + timedelta(days=meses*30)
                cur = conn.cursor()
                cur.execute("INSERT INTO contratos (id_inmueble, id_inquilino, fecha_inicio, fecha_fin, meses, monto_alquiler, monto_contrato, monto_deposito) VALUES (?,?,?,?,?,?,?,?)",
                            (id_u, id_i, f_ini, f_fin, meses, limpiar_monto(m_alq), limpiar_monto(m_con), limpiar_monto(m_dep)))
                id_c = cur.lastrowid
                
                mes_txt = f_ini.strftime("%m/%Y")
                cur.executemany("INSERT INTO deudas (id_contrato, concepto, mes_anio, monto_debe) VALUES (?,?,?,?)", [
                    (id_c, "Contrato", mes_txt, limpiar_monto(m_con)),
                    (id_c, "Depósito", mes_txt, limpiar_monto(m_dep)),
                    (id_c, "Alquiler Mes 1", mes_txt, limpiar_monto(m_alq))
                ])
                conn.commit()
                st.success("¡Contrato y deudas iniciales generadas exitosamente!")
                st.rerun()
    else: st.warning("Debe tener Inquilinos y Unidades cargadas.")
    conn.close()

elif menu == "💰 3. Cobranzas":
    st.header("Gestión de Cobros")
    conn = conectar()
    deudas = pd.read_sql_query("""
        SELECT d.id, inq.nombre, i.tipo, d.concepto, d.mes_anio, d.monto_debe, d.monto_pago 
        FROM deudas d JOIN contratos c ON d.id_contrato=c.id
        JOIN inmuebles i ON c.id_inmueble=i.id JOIN inquilinos inq ON c.id_inquilino=inq.id
        WHERE d.pagado = 0
    """, conn)
    for _, r in deudas.iterrows():
        with st.expander(f"📌 {r['nombre']} - {r['tipo']} ({r['concepto']} - {r['mes_anio']})"):
            saldo = r['monto_debe'] - r['monto_pago']
            pago = st.text_input(f"Monto a recibir", value=str(int(saldo)), key=f"p_{r['id']}")
            if st.button("Confirmar Pago", key=f"btn_{r['id']}"):
                nuevo_p = r['monto_pago'] + limpiar_monto(pago)
                conn.execute("UPDATE deudas SET monto_pago=?, pagado=?, fecha_cobro=? WHERE id=?", 
                             (nuevo_p, 1 if nuevo_p>=r['monto_debe'] else 0, date.today(), r['id']))
                conn.commit(); st.rerun()
    conn.close()

elif menu == "🚨 4. Morosos":
    st.header("Reporte de Deudores")
    conn = conectar()
    df_m = pd.read_sql_query("""
        SELECT inq.nombre as Inquilino, i.tipo as Unidad, d.concepto, d.mes_anio, (d.monto_debe - d.monto_pago) as Saldo 
        FROM deudas d JOIN contratos c ON d.id_contrato=c.id 
        JOIN inmuebles i ON c.id_inmueble=i.id 
        JOIN inquilinos inq ON c.id_inquilino=inq.id 
        WHERE d.pagado=0
    """, conn)
    if not df_m.empty:
        df_m['Saldo'] = df_m['Saldo'].apply(fmt_moneda)
        st.table(df_m)
    conn.close()

elif menu == "📊 5. Caja":
    st.header("Ingresos Realizados")
    conn = conectar()
    df_c = pd.read_sql_query("SELECT fecha_cobro as Fecha, concepto as Detalle, monto_pago as Importe FROM deudas WHERE pagado=1", conn)
    if not df_c.empty:
        df_c['Importe'] = df_c['Importe'].apply(fmt_moneda)
        st.dataframe(df_c, use_container_width=True, hide_index=True)
    conn.close()

# ==========================================
# 5. SECCIÓN 6: MAESTROS (TODO AQUÍ)
# ==========================================
elif menu == "⚙️ 6. Maestros":
    st.header("Administración de Maestros")
    t1, t2, t3, t4, t5 = st.tabs(["👤 Inquilinos", "🏢 Bloques", "🏠 Unidades", "📋 Ver Contratos", "🚀 Procesos"])
    
    with t1: # INQUILINOS
        con = conectar()
        st.subheader("Gestión de Inquilinos")
        with st.form("f_inq", clear_on_submit=True):
            c1, c2 = st.columns(2)
            n = c1.text_input("Nombre y Apellido")
            d = c2.text_input("DNI")
            w = c1.text_input("WhatsApp")
            p = c2.text_input("Procedencia")
            if st.form_submit_button("Guardar Inquilino"):
                con.execute("INSERT INTO inquilinos (nombre, dni, celular, procedencia) VALUES (?,?,?,?)", (n, d, w, p))
                con.commit(); st.rerun()
        df_inq = pd.read_sql_query("SELECT nombre, dni, celular, procedencia FROM inquilinos", con)
        st.dataframe(df_inq, use_container_width=True)
        con.close()

    with t2: # BLOQUES
        con = conectar()
        st.subheader("Gestión de Bloques")
        with st.form("f_bloque", clear_on_submit=True):
            nb = st.text_input("Nombre del Bloque (Ej: Torre A, Planta Baja)")
            if st.form_submit_button("Guardar Bloque"):
                con.execute("INSERT INTO bloques (nombre) VALUES (?)", (nb,))
                con.commit(); st.rerun()
        df_bl = pd.read_sql_query("SELECT id, nombre FROM bloques", con)
        st.table(df_bl)
        con.close()

    with t3: # UNIDADES
        con = conectar()
        st.subheader("Gestión de Unidades")
        bls = pd.read_sql_query("SELECT * FROM bloques", con)
        if not bls.empty:
            with st.form("f_uni", clear_on_submit=True):
                c1, c2 = st.columns(2)
                idb = c1.selectbox("Bloque", bls['id'].tolist(), format_func=lambda x: bls[bls['id']==x]['nombre'].values[0])
                tp = c2.text_input("Nombre Unidad (Ej: Depto 1)")
                p1, p2, p3 = st.columns(3)
                m1 = p1.text_input("Precio Alquiler Sugerido")
                m2 = p2.text_input("Costo Contrato Sugerido")
                m3 = p3.text_input("Depósito Sugerido")
                if st.form_submit_button("Guardar Unidad"):
                    con.execute("INSERT INTO inmuebles (id_bloque, tipo, precio_alquiler, costo_contrato, deposito_base) VALUES (?,?,?,?,?)", 
                                (idb, tp, limpiar_monto(m1), limpiar_monto(m2), limpiar_monto(m3)))
                    con.commit(); st.rerun()
        df_uni = pd.read_sql_query("SELECT b.nombre as Bloque, i.tipo as Unidad, i.precio_alquiler FROM inmuebles i JOIN bloques b ON i.id_bloque = b.id", con)
        st.dataframe(df_uni, use_container_width=True)
        con.close()

    with t4: # VER CONTRATOS
        st.subheader("Contratos Registrados")
        con = conectar()
        df_c = pd.read_sql_query("""
            SELECT c.id, inq.nombre as Inquilino, i.tipo as Unidad, c.fecha_inicio, c.fecha_fin, c.activo
            FROM contratos c JOIN inquilinos inq ON c.id_inquilino=inq.id
            JOIN inmuebles i ON c.id_inmueble=i.id
        """, con)
        st.dataframe(df_c, use_container_width=True, hide_index=True)
        con.close()

    with t5: # PROCESOS (Generar Cuotas)
        st.subheader("Generación de Cuotas Mensuales")
        mes_anio = st.text_input("Mes/Año a generar (Ej: Agosto 2026)")
        if st.button("PROCESAR ALQUILERES DEL MES"):
            con = conectar()
            activos = pd.read_sql_query("SELECT id, monto_alquiler FROM contratos WHERE activo=1", con)
            for _, c in activos.iterrows():
                con.execute("INSERT INTO deudas (id_contrato, concepto, mes_anio, monto_debe) VALUES (?, 'Alquiler', ?, ?)", 
                            (c['id'], mes_anio, c['monto_alquiler']))
            con.commit(); con.close(); st.success(f"Cuotas de {mes_anio} generadas.")
