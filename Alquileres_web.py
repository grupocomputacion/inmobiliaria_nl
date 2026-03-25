import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, date, timedelta
import urllib.parse
import os

# ==========================================
# 1. CONFIGURACIÓN E IDENTIDAD VISUAL
# ==========================================
st.set_page_config(
    page_title="NL Propiedades - Gestión", 
    page_icon="🏠", 
    layout="wide", 
    initial_sidebar_state="expanded"
)

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
# 2. MENÚ LATERAL
# ==========================================
with st.sidebar:
    try: st.image("logo.jpg", use_container_width=True)
    except: st.title("NL PROPIEDADES")
    st.divider()
    menu = st.radio("Navegación:", ["🏠 1. Inventario", "📝 2. Nuevo Contrato", "💰 3. Cobranzas", "🚨 4. Morosos", "📊 5. Caja", "⚙️ 6. Maestros"])
    st.divider()
    if st.button("🚨 REINICIAR SISTEMA"):
        if os.path.exists('datos_alquileres.db'): os.remove('datos_alquileres.db')
        inicializar_db()
        st.rerun()

# ==========================================
# 🏠 1. INVENTARIO (CORREGIDO: REGISTRO ÚNICO)
# ==========================================
if menu == "🏠 1. Inventario":
    st.header("Estado de Unidades")
    conn = conectar()
    # Usamos MAX(c.id) y GROUP BY para asegurar un solo registro por inmueble
    df = pd.read_sql_query("""
        SELECT i.id, b.nombre as Bloque, i.tipo as Unidad, 
               i.precio_alquiler as [Alquiler ($)], 
               i.costo_contrato as [Contrato ($)], 
               i.deposito_base as [Depósito ($)],
               c.fecha_fin, MAX(c.activo) as activo
        FROM inmuebles i
        JOIN bloques b ON i.id_bloque = b.id
        LEFT JOIN contratos c ON i.id = c.id_inmueble AND c.activo = 1
        GROUP BY i.id
    """, conn)
    conn.close()

    if not df.empty:
        def calc_estado(row):
            if pd.isna(row['activo']) or row['activo'] == 0: return "🟢 LIBRE", "HOY"
            return "🔴 OCUPADO", row['fecha_fin']
        df[['Estado', 'Disponible']] = df.apply(lambda x: pd.Series(calc_estado(x)), axis=1)
        for col in ['Alquiler ($)', 'Contrato ($)', 'Depósito ($)']:
            df[col] = df[col].apply(fmt_moneda)
        st.dataframe(df[["Bloque", "Unidad", "Estado", "Disponible", "Alquiler ($)", "Contrato ($)", "Depósito ($)"]], use_container_width=True, hide_index=True)
    else: st.info("Cargue unidades en Maestros.")

# ==========================================
# 📝 2. NUEVO CONTRATO (CON GENERACIÓN DE DEUDA AUTOMÁTICA)
# ==========================================
elif menu == "📝 2. Nuevo Contrato":
    st.header("Alta de Alquiler")
    conn = conectar()
    inm = pd.read_sql_query("SELECT i.id, b.nombre || ' - ' || i.tipo as ref, i.precio_alquiler, i.costo_contrato, i.deposito_base FROM inmuebles i JOIN bloques b ON i.id_bloque=b.id", conn)
    inq = pd.read_sql_query("SELECT * FROM inquilinos", conn)
    
    if not inm.empty and not inq.empty:
        # Formulario con llave para resetear campos
        with st.form("nuevo_con", clear_on_submit=True):
            c1, c2 = st.columns(2)
            sel_inm = c1.selectbox("Unidad", inm['id'].tolist(), format_func=lambda x: inm[inm['id']==x]['ref'].values[0])
            sel_inq = c2.selectbox("Inquilino", inq['id'].tolist(), format_func=lambda x: inq[inq['id']==x]['nombre'].values[0])
            f_ini = c1.date_input("Fecha Inicio", date.today())
            meses = c2.number_input("Duración (Meses)", min_value=1, value=6)
            
            datos_u = inm[inm['id']==sel_inm].iloc[0]
            m_alq = c1.text_input("Monto Alquiler", value=str(int(datos_u['precio_alquiler'])))
            m_con = c2.text_input("Monto Contrato", value=str(int(datos_u['costo_contrato'])))
            m_dep = c1.text_input("Monto Depósito", value=str(int(datos_u['deposito_base'])))
            
            if st.form_submit_button("Confirmar y Generar Deudas"):
                f_fin = f_ini + timedelta(days=meses*30)
                cur = conn.cursor()
                # 1. Grabar Contrato
                cur.execute("""INSERT INTO contratos 
                    (id_inmueble, id_inquilino, fecha_inicio, fecha_fin, meses, activo, monto_alquiler, monto_contrato, monto_deposito) 
                    VALUES (?,?,?,?,?,1,?,?,?)""",
                    (sel_inm, sel_inq, f_ini, f_fin, meses, limpiar_monto(m_alq), limpiar_monto(m_con), limpiar_monto(m_dep)))
                id_generado = cur.lastrowid
                
                # 2. Grabar Deudas Iniciales Automáticas
                mes_actual = f_ini.strftime("%B %Y")
                deudas_iniciales = [
                    (id_generado, "Costo Contrato", mes_actual, limpiar_monto(m_con)),
                    (id_generado, "Depósito Garantía", mes_actual, limpiar_monto(m_dep)),
                    (id_generado, "Alquiler Mes 1", mes_actual, limpiar_monto(m_alq))
                ]
                cur.executemany("INSERT INTO deudas (id_contrato, concepto, mes_anio, monto_debe) VALUES (?,?,?,?)", deudas_iniciales)
                
                conn.commit()
                st.success(f"Contrato #{id_generado} creado. Deudas iniciales cargadas en Cobranzas.")
                st.rerun()
    conn.close()

# ==========================================
# 💰 3. COBRANZAS / 🚨 4. MOROSOS / 📊 5. CAJA (Se mantienen igual)
# ==========================================
elif menu == "💰 3. Cobranzas":
    st.header("Cobros Pendientes")
    conn = conectar()
    deudas = pd.read_sql_query("""
        SELECT d.id, inq.nombre, i.tipo, d.concepto, d.mes_anio, d.monto_debe, d.monto_pago 
        FROM deudas d JOIN contratos c ON d.id_contrato=c.id
        JOIN inmuebles i ON c.id_inmueble=i.id JOIN inquilinos inq ON c.id_inquilino=inq.id
        WHERE d.pagado = 0
    """, conn)
    for _, r in deudas.iterrows():
        with st.expander(f"{r['nombre']} - {r['tipo']} ({r['concepto']})"):
            saldo = r['monto_debe'] - r['monto_pago']
            pago = st.text_input(f"Cobrar", value=str(int(saldo)), key=f"p_{r['id']}")
            if st.button("Confirmar Pago", key=f"btn_{r['id']}"):
                nuevo_p = r['monto_pago'] + limpiar_monto(pago)
                conn.execute("UPDATE deudas SET monto_pago=?, pagado=?, fecha_cobro=? WHERE id=?", (nuevo_p, 1 if nuevo_p>=r['monto_debe'] else 0, date.today(), r['id']))
                conn.commit(); st.rerun()
    conn.close()

elif menu == "🚨 4. Morosos":
    st.header("Deudores")
    conn = conectar()
    df_m = pd.read_sql_query("SELECT inq.nombre as Inquilino, i.tipo as Unidad, d.concepto, d.mes_anio, (d.monto_debe - d.monto_pago) as Saldo FROM deudas d JOIN contratos c ON d.id_contrato=c.id JOIN inmuebles i ON c.id_inmueble=i.id JOIN inquilinos inq ON c.id_inquilino=inq.id WHERE d.pagado=0", conn)
    if not df_m.empty: st.table(df_m)
    conn.close()

elif menu == "📊 5. Caja":
    st.header("Ingresos")
    conn = conectar()
    df_c = pd.read_sql_query("SELECT fecha_cobro, concepto, monto_pago FROM deudas WHERE pagado=1", conn)
    if not df_c.empty: st.dataframe(df_c, use_container_width=True)
    conn.close()

# ==========================================
# ⚙️ 6. MAESTROS (CORREGIDO: SECCIÓN CONTRATOS)
# ==========================================
elif menu == "⚙️ 6. Maestros":
    st.header("Administración")
    t1, t2, t3, t4, t5 = st.tabs(["👤 Inquilinos", "🏢 Bloques", "🏠 Unidades", "📋 Ver Contratos", "🚀 Procesos"])
    
    with t4: # CONSULTA DE CONTRATOS
        st.write("### Listado de Contratos")
        con = conectar()
        query_c = """
            SELECT c.id, inq.nombre as Inquilino, i.tipo as Unidad, c.fecha_inicio, c.fecha_fin, 
                   c.monto_alquiler, c.activo
            FROM contratos c
            JOIN inquilinos inq ON c.id_inquilino = inq.id
            JOIN inmuebles i ON c.id_inmueble = i.id
        """
        df_contratos = pd.read_sql_query(query_c, con)
        if not df_contratos.empty:
            st.dataframe(df_contratos, use_container_width=True, hide_index=True)
            if st.button("🗑️ Eliminar Contrato Seleccionado"):
                st.warning("Seleccione el ID arriba para borrar (Función en desarrollo)")
        con.close()

    with t1: # INQUILINOS (Con edición)
        con = conectar()
        inqs = pd.read_sql_query("SELECT * FROM inquilinos", con)
        c_i1, c_i2 = st.columns(2)
        with c_i1:
            st.write("#### Nuevo Inquilino")
            with st.form("f_inq", clear_on_submit=True):
                n = st.text_input("Nombre")
                d = st.text_input("DNI")
                w = st.text_input("WhatsApp")
                if st.form_submit_button("Guardar"):
                    con.execute("INSERT INTO inquilinos (nombre, dni, celular) VALUES (?,?,?)", (n, d, w))
                    con.commit(); st.rerun()
        con.close()
