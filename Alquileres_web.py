import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, date, timedelta
import os

# ==========================================
# 1. CONFIGURACIÓN E IDENTIDAD VISUAL
# ==========================================
st.set_page_config(page_title="NL Propiedades - Sistema de Gestión", layout="wide", initial_sidebar_state="expanded")

# Estilo Dorado y Negro
st.markdown("""
    <style>
    .stButton>button { background-color: #D4AF37; color: black; border-radius: 5px; font-weight: bold; width: 100%; }
    .stButton>button:hover { background-color: #B8860B; color: white; }
    h1, h2, h3, h4 { color: #D4AF37; }
    [data-testid="stSidebar"] { background-color: #111; }
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 2. MOTOR DE BASE DE DATOS Y MIGRACIONES
# ==========================================
def conectar():
    return sqlite3.connect('datos_alquileres.db', check_same_thread=False, timeout=20)

conn = conectar()
cursor = conn.cursor()

# Creación de tablas base
cursor.execute("CREATE TABLE IF NOT EXISTS bloques (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT UNIQUE)")
cursor.execute("CREATE TABLE IF NOT EXISTS inmuebles (id INTEGER PRIMARY KEY AUTOINCREMENT, id_bloque INTEGER, tipo TEXT, precio_alquiler INTEGER, costo_contrato INTEGER, deposito_base INTEGER)")
cursor.execute("CREATE TABLE IF NOT EXISTS inquilinos (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT, celular TEXT, dni TEXT, direccion TEXT, emergencia_contacto TEXT, procedencia TEXT, grupo TEXT)")
cursor.execute("CREATE TABLE IF NOT EXISTS contratos (id INTEGER PRIMARY KEY AUTOINCREMENT, id_inmueble INTEGER, id_inquilino INTEGER, fecha_inicio DATE, fecha_fin DATE, meses INTEGER, activo INTEGER DEFAULT 1, monto_alquiler INTEGER, monto_contrato INTEGER, monto_deposito INTEGER)")
cursor.execute("CREATE TABLE IF NOT EXISTS deudas (id INTEGER PRIMARY KEY AUTOINCREMENT, id_contrato INTEGER, concepto TEXT, mes_anio TEXT, monto_debe INTEGER, monto_pago INTEGER DEFAULT 0, pagado INTEGER DEFAULT 0, fecha_cobro DATE)")
conn.commit()

# MIGRACIÓN: Asegurar que existan todas las columnas (Previene errores de consulta)
migraciones = {
    "inquilinos": ["celular", "dni", "direccion", "emergencia_contacto", "procedencia", "grupo"],
    "inmuebles": ["precio_alquiler", "costo_contrato", "deposito_base"]
}
for tabla, cols in migraciones.items():
    for col in cols:
        try: cursor.execute(f"ALTER TABLE {tabla} ADD COLUMN {col} TEXT")
        except: pass
conn.commit()

# Utilidades de formato
def fmt_moneda(v): return f"$ {int(v or 0):,}".replace(",", ".")
def limpiar_monto(t): return int(str(t).replace('$', '').replace('.', '').replace(',', '').strip() or 0)

# ==========================================
# 3. BARRA LATERAL (CONTROL DE NAVEGACIÓN)
# ==========================================
with st.sidebar:
    try: st.image("logo.jpg", use_container_width=True)
    except: st.title("NL PROPIEDADES")
    
    st.divider()
    # ESTE ES EL SELECTOR QUE DISPARA TODO EL SISTEMA
    menu = st.radio("SELECCIONE FUNCIÓN:", 
                    ["🏠 1. Inventario", 
                     "📝 2. Nuevo Contrato", 
                     "💰 3. Cobranzas", 
                     "🚨 4. Morosos", 
                     "📊 5. Caja", 
                     "⚙️ 6. Maestros"])
    
    st.divider()
    if st.button("🚨 REINICIAR TODA LA BASE"):
        if os.path.exists('datos_alquileres.db'): os.remove('datos_alquileres.db')
        st.rerun()

# ==========================================
# 4. LÓGICA DE SECCIONES (SISTEMA INTEGRAL)
# ==========================================

# --- SECCIÓN 1: INVENTARIO ---
if menu == "🏠 1. Inventario":
    st.header("1. Inventario y Disponibilidad")
    query = """
        SELECT b.nombre as Bloque, i.tipo as Unidad, i.precio_alquiler as Alquiler, 
               i.costo_contrato as Contrato, i.deposito_base as Deposito,
               MAX(c.fecha_fin) as Vencimiento, MAX(c.activo) as ocupado
        FROM inmuebles i 
        JOIN bloques b ON i.id_bloque = b.id 
        LEFT JOIN contratos c ON i.id = c.id_inmueble AND c.activo = 1 
        GROUP BY i.id
    """
    df_inv = pd.read_sql_query(query, conn)
    if not df_inv.empty:
        df_inv['Estado'] = df_inv['ocupado'].apply(lambda x: "🔴 OCUPADO" if x == 1 else "🟢 LIBRE")
        st.dataframe(df_inv[["Bloque", "Unidad", "Estado", "Vencimiento", "Alquiler", "Contrato", "Deposito"]], use_container_width=True, hide_index=True)
    else: st.info("No hay unidades cargadas en la sección 6.")

# --- SECCIÓN 2: NUEVO CONTRATO ---
if menu == "📝 2. Nuevo Contrato":
    st.header("2. Alta de Contrato y Deudas Iniciales")
    unidades = pd.read_sql_query("SELECT i.id, b.nombre || ' - ' || i.tipo as ref, i.precio_alquiler, i.costo_contrato, i.deposito_base FROM inmuebles i JOIN bloques b ON i.id_bloque = b.id", conn)
    inquilinos = pd.read_sql_query("SELECT id, nombre FROM inquilinos", conn)
    
    if not unidades.empty and not inquilinos.empty:
        with st.form("form_alta_contrato", clear_on_submit=True):
            col1, col2 = st.columns(2)
            u_id = col1.selectbox("Unidad", unidades['id'].tolist(), format_func=lambda x: unidades[unidades['id']==x]['ref'].values[0])
            i_id = col2.selectbox("Inquilino", inquilinos['id'].tolist(), format_func=lambda x: inquilinos[inquilinos['id']==x]['nombre'].values[0])
            f_ini = col1.date_input("Inicio", datetime.now())
            meses = col2.number_input("Meses", 1, 60, 6)
            
            u_data = unidades[unidades['id']==u_id].iloc[0]
            m_alq = col1.text_input("Alquiler Mensual", value=str(u_data['precio_alquiler']))
            m_con = col2.text_input("Costo Contrato", value=str(u_data['costo_contrato']))
            m_dep = col1.text_input("Depósito", value=str(u_data['deposito_base']))
            
            if st.form_submit_button("GRABAR Y GENERAR COBROS"):
                f_fin = f_ini + timedelta(days=meses*30)
                cursor.execute("INSERT INTO contratos (id_inmueble, id_inquilino, fecha_inicio, fecha_fin, meses, monto_alquiler, monto_contrato, monto_deposito) VALUES (?,?,?,?,?,?,?,?)", 
                               (u_id, i_id, f_ini, f_fin, meses, limpiar_monto(m_alq), limpiar_monto(m_con), limpiar_monto(m_dep)))
                cid = cursor.lastrowid
                # Deudas automáticas
                mes_anio = f_ini.strftime("%m/%Y")
                cursor.executemany("INSERT INTO deudas (id_contrato, concepto, mes_anio, monto_debe) VALUES (?,?,?,?)", 
                                   [(cid, "Contrato Inicial", mes_anio, limpiar_monto(m_con)), 
                                    (cid, "Depósito Garantía", mes_anio, limpiar_monto(m_dep)), 
                                    (cid, f"Alquiler {mes_anio}", mes_anio, limpiar_monto(m_alq))])
                conn.commit()
                st.success("Contrato grabado. Revise 'Cobranzas' para registrar pagos.")
    else: st.warning("Faltan Inquilinos o Unidades en Maestros.")

# --- SECCIÓN 3: COBRANZAS ---
if menu == "💰 3. Cobranzas":
    st.header("3. Registro de Cobranzas")
    deudas = pd.read_sql_query("""
        SELECT d.id, inq.nombre, i.tipo, d.concepto, d.mes_anio, d.monto_debe, d.monto_pago 
        FROM deudas d JOIN contratos c ON d.id_contrato=c.id 
        JOIN inmuebles i ON c.id_inmueble=i.id JOIN inquilinos inq ON c.id_inquilino=inq.id 
        WHERE d.pagado = 0
    """, conn)
    if not deudas.empty:
        for _, r in deudas.iterrows():
            with st.expander(f"💰 {r['nombre']} - {r['tipo']} ({r['concepto']})"):
                saldo = r['monto_debe'] - r['monto_pago']
                monto_cobro = st.text_input(f"Monto a recibir", value=str(int(saldo)), key=f"d_{r['id']}")
                if st.button("Confirmar Cobro", key=f"b_{r['id']}"):
                    nuevo_p = r['monto_pago'] + limpiar_monto(monto_cobro)
                    cursor.execute("UPDATE deudas SET monto_pago=?, pagado=?, fecha_cobro=? WHERE id=?", 
                                   (nuevo_p, 1 if nuevo_p >= r['monto_debe'] else 0, datetime.now(), r['id']))
                    conn.commit(); st.rerun()
    else: st.info("No hay deudas pendientes de cobro.")

# --- SECCIÓN 4: MOROSOS ---
if menu == "🚨 4. Morosos":
    st.header("4. Reporte de Morosos")
    df_morosos = pd.read_sql_query("""
        SELECT inq.nombre as Inquilino, i.tipo as Unidad, d.concepto as Item, d.mes_anio as Mes, (d.monto_debe - d.monto_pago) as Saldo 
        FROM deudas d JOIN contratos c ON d.id_contrato=c.id 
        JOIN inmuebles i ON c.id_inmueble=i.id JOIN inquilinos inq ON c.id_inquilino=inq.id 
        WHERE d.pagado = 0
    """, conn)
    if not df_morosos.empty:
        df_morosos['Saldo'] = df_morosos['Saldo'].apply(fmt_moneda)
        st.table(df_morosos)
    else: st.success("¡Todo al día! No hay morosos.")

# --- SECCIÓN 5: CAJA ---
if menu == "📊 5. Caja":
    st.header("5. Ingresos de Caja")
    df_caja = pd.read_sql_query("SELECT fecha_cobro as Fecha, concepto as Detalle, monto_pago as Importe FROM deudas WHERE pagado=1", conn)
    if not df_caja.empty:
        st.metric("Total en Caja", fmt_moneda(df_caja['Importe'].sum()))
        st.dataframe(df_caja, use_container_width=True)
    else: st.info("No hay ingresos registrados aún.")

# --- SECCIÓN 6: MAESTROS ---
if menu == "⚙️ 6. Maestros":
    st.header("6. Configuración de Maestros")
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["👥 Inquilinos", "🏢 Bloques", "🏠 Unidades", "📋 Contratos", "🚀 Procesos"])
    
    with tab1: # INQUILINOS
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("Alta / Edición")
            modo = st.radio("Acción Inquilino", ["Nuevo", "Editar"], horizontal=True)
            v_id, v_nom, v_dni, v_cel = None, "", "", ""
            if modo == "Editar":
                inqs_all = pd.read_sql_query("SELECT * FROM inquilinos", conn)
                if not inqs_all.empty:
                    sel_i = st.selectbox("Elegir para editar", inqs_all['id'].tolist(), format_func=lambda x: inqs_all[inqs_all['id']==x]['nombre'].values[0])
                    f = inqs_all[inqs_all['id']==sel_i].iloc[0]
                    v_id, v_nom, v_dni, v_cel = f['id'], f['nombre'], f['dni'], f['celular']
            
            with st.form("f_inq", clear_on_submit=True):
                n_nom = st.text_input("Nombre Completo", value=v_nom)
                n_dni = st.text_input("DNI / Documento", value=v_dni)
                n_cel = st.text_input("WhatsApp", value=v_cel)
                if st.form_submit_button("Guardar Inquilino"):
                    if modo == "Nuevo": cursor.execute("INSERT INTO inquilinos (nombre, dni, celular) VALUES (?,?,?)", (n_nom, n_dni, n_cel))
                    else: cursor.execute("UPDATE inquilinos SET nombre=?, dni=?, celular=? WHERE id=?", (n_nom, n_dni, n_cel, v_id))
                    conn.commit(); st.rerun()
        with c2:
            st.subheader("Listado y Borrado")
            df_i = pd.read_sql_query("SELECT id, nombre, dni FROM inquilinos", conn)
            st.dataframe(df_i, use_container_width=True, hide_index=True)
            id_borrar = st.number_input("ID a borrar", step=1, value=0)
            if st.button("🗑️ Eliminar Inquilino"):
                cursor.execute(f"DELETE FROM inquilinos WHERE id={id_borrar}"); conn.commit(); st.rerun()

    with tab2: # BLOQUES
        with st.form("f_bloque"):
            nb = st.text_input("Nombre del Bloque (Ej: Planta Baja)")
            if st.form_submit_button("Guardar Bloque"):
                cursor.execute("INSERT INTO bloques (nombre) VALUES (?)", (nb,))
                conn.commit(); st.rerun()
        st.table(pd.read_sql_query("SELECT * FROM bloques", conn))

    with tab3: # UNIDADES
        bls = pd.read_sql_query("SELECT * FROM bloques", conn)
        if not bls.empty:
            with st.form("f_uni"):
                b_id = st.selectbox("Elegir Bloque", bls['id'].tolist(), format_func=lambda x: bls[bls['id']==x]['nombre'].values[0])
                tip = st.text_input("Nombre Unidad (Ej: Local 1)")
                p1, p2, p3 = st.columns(3)
                m_a = p1.text_input("Alquiler Sugerido")
                m_c = p2.text_input("Contrato Sugerido")
                m_d = p3.text_input("Depósito Sugerido")
                if st.form_submit_button("Guardar Unidad"):
                    cursor.execute("INSERT INTO inmuebles (id_bloque, tipo, precio_alquiler, costo_contrato, deposito_base) VALUES (?,?,?,?,?)", (b_id, tip, limpiar_monto(m_a), limpiar_monto(m_c), limpiar_monto(m_d)))
                    conn.commit(); st.rerun()
        st.dataframe(pd.read_sql_query("SELECT i.id, b.nombre as Bloque, i.tipo as Unidad FROM inmuebles i JOIN bloques b ON i.id_bloque=b.id", conn))

    with tab4: # VER/BORRAR CONTRATOS
        df_c = pd.read_sql_query("""
            SELECT c.id, inq.nombre as Inquilino, i.tipo as Unidad, c.fecha_inicio, c.fecha_fin, c.activo 
            FROM contratos c JOIN inquilinos inq ON c.id_inquilino=inq.id 
            JOIN inmuebles i ON c.id_inmueble=i.id
        """, conn)
        st.dataframe(df_c, use_container_width=True)
        id_c_borrar = st.number_input("ID Contrato a eliminar", step=1, value=0)
        if st.button("🗑️ Eliminar Contrato"):
            cursor.execute(f"DELETE FROM deudas WHERE id_contrato={id_c_borrar}")
            cursor.execute(f"DELETE FROM contratos WHERE id={id_c_borrar}")
            conn.commit(); st.rerun()

    with tab5: # GENERAR CUOTAS
        st.subheader("🚀 Generación Masiva")
        mes_gen = st.text_input("Mes/Año (Ej: 05/2026)")
        if st.button("Generar Alquileres"):
            activos = pd.read_sql_query("SELECT id, monto_alquiler FROM contratos WHERE activo=1", conn)
            for _, c in activos.iterrows():
                cursor.execute("INSERT INTO deudas (id_contrato, concepto, mes_anio, monto_debe) VALUES (?, 'Alquiler Mensual', ?, ?)", (c['id'], mes_gen, c['monto_alquiler']))
            conn.commit(); st.success(f"Cuotas de {mes_gen} generadas."); st.rerun()

conn.close()
