import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, date, timedelta
import os

# ==========================================
# 1. CONFIGURACIÓN E IDENTIDAD VISUAL
# ==========================================
st.set_page_config(page_title="NL Propiedades - Gestión", page_icon="🏠", layout="wide")

# Cambiar a True cuando el sistema ya tenga datos reales para ocultar el botón de reset
ES_PRODUCCION = False 

st.markdown("""
    <style>
    .stButton>button { background-color: #D4AF37; color: black; border-radius: 5px; font-weight: bold; width: 100%; }
    .stButton>button:hover { background-color: #B8860B; color: white; }
    h1, h2, h3, h4 { color: #D4AF37; }
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 2. MOTOR DE BASE DE DATOS Y MIGRACIONES (PROTECCIÓN DE DATOS)
# ==========================================
def conectar():
    return sqlite3.connect('datos_alquileres.db', check_same_thread=False, timeout=20)

def inicializar_db():
    conn = conectar()
    c = conn.cursor()
    
    # Crear tablas base si no existen
    c.execute("CREATE TABLE IF NOT EXISTS bloques (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT UNIQUE)")
    c.execute("""CREATE TABLE IF NOT EXISTS inmuebles (
        id INTEGER PRIMARY KEY AUTOINCREMENT, id_bloque INTEGER, tipo TEXT, 
        precio_alquiler INTEGER, costo_contrato INTEGER, deposito_base INTEGER, UNIQUE(id_bloque, tipo))""")
    c.execute("CREATE TABLE IF NOT EXISTS inquilinos (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT)")
    c.execute("""CREATE TABLE IF NOT EXISTS contratos (
        id INTEGER PRIMARY KEY AUTOINCREMENT, id_inmueble INTEGER, id_inquilino INTEGER, 
        fecha_inicio DATE, fecha_fin DATE, meses INTEGER, activo INTEGER DEFAULT 1, 
        monto_alquiler INTEGER, monto_contrato INTEGER, monto_deposito INTEGER)""")
    c.execute("""CREATE TABLE IF NOT EXISTS deudas (
        id INTEGER PRIMARY KEY AUTOINCREMENT, id_contrato INTEGER, concepto TEXT, 
        mes_anio TEXT, monto_debe INTEGER, monto_pago INTEGER DEFAULT 0, pagado INTEGER DEFAULT 0, fecha_cobro DATE)""")

    # --- MIGRACIÓN AUTOMÁTICA (Agrega columnas nuevas SIN borrar datos) ---
    # Diccionario de columnas requeridas por tabla
    migraciones = {
        "inquilinos": [
            ("celular", "TEXT"), ("dni", "TEXT"), ("direccion", "TEXT"), 
            ("emergencia_contacto", "TEXT"), ("procedencia", "TEXT"), ("grupo", "TEXT")
        ],
        "inmuebles": [
            ("precio_alquiler", "INTEGER"), ("costo_contrato", "INTEGER"), ("deposito_base", "INTEGER")
        ]
    }

    for tabla, columnas in migraciones.items():
        # Obtenemos las columnas actuales de la tabla
        cursor = c.execute(f"PRAGMA table_info({tabla})")
        columnas_existentes = [row[1] for row in cursor.fetchall()]
        
        for col_nombre, col_tipo in columnas:
            if col_nombre not in columnas_existentes:
                try:
                    c.execute(f"ALTER TABLE {tabla} ADD COLUMN {col_nombre} {col_tipo}")
                except Exception as e:
                    pass # Ya existe o error controlado

    conn.commit()
    conn.close()

# Inicializamos el motor (No borra nada, solo actualiza la estructura)
inicializar_db()

# --- UTILIDADES ---
def fmt_moneda(valor):
    try: return f"$ {int(float(valor or 0)):,}".replace(",", ".")
    except: return "$ 0"

def limpiar_monto(texto):
    if not texto: return 0
    try: return int(float(str(texto).replace('$', '').replace('.', '').replace(',', '').strip()))
    except: return 0

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
        if st.button("🚨 RESETEAR (BORRAR TODO)"):
            if os.path.exists('datos_alquileres.db'): os.remove('datos_alquileres.db')
            inicializar_db()
            st.rerun()

# ==========================================
# 4. SECCIONES (SINTAXIS SQL CORREGIDA)
# ==========================================

if menu == "🏠 1. Inventario":
    st.header("Inventario de Unidades")
    conn = conectar()
    query = """
        SELECT b.nombre as Bloque, i.tipo as Unidad, 
               i.precio_alquiler, i.costo_contrato, i.deposito_base,
               MAX(c.fecha_fin) as Vencimiento, MAX(c.activo) as ocupado
        FROM inmuebles i
        JOIN bloques b ON i.id_bloque = b.id
        LEFT JOIN contratos c ON i.id = c.id_inmueble AND c.activo = 1
        GROUP BY i.id
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    if not df.empty:
        df['Estado'] = df['ocupado'].apply(lambda x: "🔴 OCUPADO" if x == 1 else "🟢 LIBRE")
        df['Alquiler Sug.'] = df['precio_alquiler'].apply(fmt_moneda)
        st.dataframe(df[["Bloque", "Unidad", "Estado", "Vencimiento", "Alquiler Sug."]], use_container_width=True, hide_index=True)
    else: st.info("Sin unidades.")

elif menu == "📝 2. Nuevo Contrato":
    st.header("Alta de Alquiler")
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
            m_alq = c1.text_input("Monto Alquiler", value=str(int(u_data['precio_alquiler'] or 0)))
            m_con = c2.text_input("Monto Contrato", value=str(int(u_data['costo_contrato'] or 0)))
            m_dep = c1.text_input("Monto Depósito", value=str(int(u_data['deposito_base'] or 0)))
            
            if st.form_submit_button("GRABAR CONTRATO"):
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
                conn.commit(); st.success("Guardado."); st.rerun()
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
        with st.expander(f"💰 {r['nombre']} - {r['tipo']} ({r['concepto']})"):
            saldo = r['monto_debe'] - r['monto_pago']
            pago = st.text_input(f"Cobrar", value=str(int(saldo)), key=f"p_{r['id']}")
            if st.button("Cobrar Ahora", key=f"btn_{r['id']}"):
                nuevo_p = r['monto_pago'] + limpiar_monto(pago)
                conn.execute("UPDATE deudas SET monto_pago=?, pagado=?, fecha_cobro=? WHERE id=?", (nuevo_p, 1 if nuevo_p>=r['monto_debe'] else 0, date.today(), r['id']))
                conn.commit(); st.rerun()
    conn.close()

elif menu == "🚨 4. Morosos":
    st.header("Reporte Morosidad")
    conn = conectar()
    df_m = pd.read_sql_query("""
        SELECT inq.nombre as Inquilino, i.tipo as Unidad, d.concepto, d.mes_anio as Mes, (d.monto_debe - d.monto_pago) as Saldo 
        FROM deudas d JOIN contratos c ON d.id_contrato=c.id 
        JOIN inmuebles i ON c.id_inmueble=i.id JOIN inquilinos inq ON c.id_inquilino=inq.id 
        WHERE d.pagado=0""", conn)
    if not df_m.empty:
        df_m['Saldo'] = df_m['Saldo'].apply(fmt_moneda)
        st.dataframe(df_m, use_container_width=True, hide_index=True)
    conn.close()

elif menu == "📊 5. Caja":
    st.header("Ingresos")
    conn = conectar()
    df_c = pd.read_sql_query("SELECT fecha_cobro as Fecha, concepto, monto_pago as Importe FROM deudas WHERE pagado=1", conn)
    if not df_c.empty:
        st.metric("Total", fmt_moneda(df_c['Importe'].sum()))
        st.dataframe(df_c, use_container_width=True)
    conn.close()

# ==========================================
# 5. SECCIÓN 6: MAESTROS (CARGA COMPLETA)
# ==========================================
elif menu == "⚙️ 6. Maestros":
    st.header("Administración")
    t1, t2, t3, t4 = st.tabs(["👤 Inquilinos", "🏢 Bloques", "🏠 Unidades", "📋 Contratos"])
    
    with t1:
        con = conectar()
        st.subheader("Carga Inquilinos")
        with st.form("fi", clear_on_submit=True):
            ca, cb = st.columns(2)
            n, d = ca.text_input("Nombre"), cb.text_input("DNI")
            c, p = ca.text_input("WhatsApp"), cb.text_input("Procedencia")
            g, e = ca.text_input("Grupo"), cb.text_input("Emergencia")
            if st.form_submit_button("Guardar Inquilino"):
                con.execute("INSERT INTO inquilinos (nombre, celular, dni, procedencia, grupo, emergencia_contacto) VALUES (?,?,?,?,?,?)", (n, c, d, p, g, e))
                con.commit(); st.rerun()
        df_inq = pd.read_sql_query("SELECT nombre, dni, celular, procedencia, grupo FROM inquilinos", con)
        st.dataframe(df_inq, use_container_width=True, hide_index=True)
        con.close()

    with t2:
        con = conectar()
        st.subheader("Carga Bloques")
        with st.form("fb", clear_on_submit=True):
            nb = st.text_input("Nuevo Bloque")
            if st.form_submit_button("Guardar"):
                con.execute("INSERT INTO bloques (nombre) VALUES (?)", (nb,))
                con.commit(); st.rerun()
        st.table(pd.read_sql_query("SELECT id, nombre FROM bloques", con))
        con.close()

    with t3:
        con = conectar()
        st.subheader("Carga Unidades")
        bls = pd.read_sql_query("SELECT * FROM bloques", con)
        if not bls.empty:
            with st.form("fu", clear_on_submit=True):
                ca, cb = st.columns(2)
                idb = ca.selectbox("Bloque", bls['id'].tolist(), format_func=lambda x: bls[bls['id']==x]['nombre'].values[0])
                tp = cb.text_input("Unidad")
                m1, m2, m3 = st.columns(3)
                p1 = m1.text_input("Alquiler")
                p2 = m2.text_input("Contrato")
                p3 = m3.text_input("Depósito")
                if st.form_submit_button("Guardar Unidad"):
                    con.execute("INSERT INTO inmuebles (id_bloque, tipo, precio_alquiler, costo_contrato, deposito_base) VALUES (?,?,?,?,?)", 
                                (idb, tp, limpiar_monto(p1), limpiar_monto(p2), limpiar_monto(p3)))
                    con.commit(); st.rerun()
        df_u = pd.read_sql_query("SELECT b.nombre as Bloque, i.tipo as Unidad, i.precio_alquiler FROM inmuebles i JOIN bloques b ON i.id_bloque = b.id", con)
        st.dataframe(df_u, use_container_width=True)
        con.close()

    with t4:
        st.subheader("Contratos")
        con = conectar()
        df_c = pd.read_sql_query("""
            SELECT c.id, inq.nombre as Inquilino, i.tipo as Unidad, c.fecha_inicio, c.fecha_fin, c.activo
            FROM contratos c JOIN inquilinos inq ON c.id_inquilino=inq.id
            JOIN inmuebles i ON c.id_inmueble=i.id""", con)
        st.dataframe(df_c, use_container_width=True)
        con.close()
