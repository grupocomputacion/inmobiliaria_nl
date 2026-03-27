import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, date, timedelta
import os
import io

# ==========================================
# 1. IDENTIDAD Y CONFIGURACIÓN (V.2.8)
# ==========================================
st.set_page_config(page_title="NL INMOBILIARIA - V.2.8", layout="wide")
st.cache_data.clear()

st.markdown("""
    <style>
    .stButton>button { background-color: #D4AF37; color: black; font-weight: bold; width: 100%; border-radius: 5px; }
    h1, h2, h3, h4 { color: #D4AF37; }
    [data-testid="stSidebar"] { background-color: #111; border-right: 1px solid #D4AF37; }
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 2. MOTOR DE DATOS (MIGRACIÓN DEFENSIVA)
# ==========================================
def db_query(sql, params=(), commit=False):
    try:
        with sqlite3.connect('datos_alquileres.db', check_same_thread=False) as conn:
            if commit:
                cur = conn.cursor()
                cur.execute(sql, params)
                conn.commit()
                return cur.lastrowid
            return pd.read_sql_query(sql, conn, params=params)
    except Exception as e:
        return None

def inicializar_y_migrar():
    # Creamos tablas base
    db_query("CREATE TABLE IF NOT EXISTS bloques (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT UNIQUE)", commit=True)
    db_query("CREATE TABLE IF NOT EXISTS inquilinos (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT, dni TEXT, celular TEXT, emergencia TEXT, procedencia TEXT, grupo TEXT)", commit=True)
    db_query("CREATE TABLE IF NOT EXISTS inmuebles (id INTEGER PRIMARY KEY AUTOINCREMENT, id_bloque INTEGER, tipo TEXT, precio_alquiler INTEGER, costo_contrato INTEGER, deposito_base INTEGER)", commit=True)
    db_query("CREATE TABLE IF NOT EXISTS contratos (id INTEGER PRIMARY KEY AUTOINCREMENT, id_inmueble INTEGER, id_inquilino INTEGER, fecha_inicio DATE, fecha_fin DATE, monto_alquiler INTEGER, activo INTEGER DEFAULT 1)", commit=True)
    db_query("CREATE TABLE IF NOT EXISTS deudas (id INTEGER PRIMARY KEY AUTOINCREMENT, id_contrato INTEGER, concepto TEXT, monto_debe INTEGER, monto_pago INTEGER DEFAULT 0, pagado INTEGER DEFAULT 0, fecha_pago DATE)", commit=True)
    
    # MIGRACIÓN: Agregar campos nuevos a bloques (Inmuebles) sin romper lo anterior
    columnas_nuevas = [("bloques", "direccion", "TEXT"), ("bloques", "barrio", "TEXT"), ("bloques", "localidad", "TEXT")]
    with sqlite3.connect('datos_alquileres.db') as conn:
        for tabla, col, tipo in columnas_nuevas:
            try: conn.execute(f"ALTER TABLE {tabla} ADD COLUMN {col} {tipo}")
            except: pass

inicializar_y_migrar()

def cl(t): return int(str(t).replace('$', '').replace('.', '').replace(',', '').strip() or 0)
def f_m(v): return f"{int(v or 0):,}".replace(",", ".")

# ==========================================
# 3. BARRA LATERAL
# ==========================================
with st.sidebar:
    if os.path.exists("alquileres.jpg"): st.image("alquileres.jpg", use_container_width=True)
    st.info("🚀 VERSIÓN: V.2.8 - PERSISTENTE")
    menu = st.radio("MENÚ:", ["🏠 Inventario", "📝 Nuevo Contrato", "💰 Cobranzas", "📊 Caja", "⚙️ Maestros"])
    if st.button("🚨 RESET TOTAL"):
        if os.path.exists('datos_alquileres.db'): os.remove('datos_alquileres.db')
        st.rerun()

# ==========================================
# 4. SECCIONES
# ==========================================

if menu == "🏠 Inventario":
    st.header("Inventario de Unidades")
    query = """
        SELECT b.nombre as Inmueble, b.direccion as Dirección, i.tipo as Unidad, i.precio_alquiler,
        CASE WHEN c.activo = 1 THEN '🔴 OCUPADO' ELSE '🟢 LIBRE' END as Estado
        FROM inmuebles i JOIN bloques b ON i.id_bloque = b.id
        LEFT JOIN contratos c ON i.id = c.id_inmueble AND c.activo = 1
    """
    df = db_query(query)
    if df is not None:
        df['precio_alquiler'] = df['precio_alquiler'].apply(f_m)
        st.dataframe(df, use_container_width=True, hide_index=True)

elif menu == "📝 Nuevo Contrato":
    st.header("Nuevo Contrato")
    u_df = db_query("SELECT i.id, b.nombre || ' - ' || i.tipo as ref, i.precio_alquiler FROM inmuebles i JOIN bloques b ON i.id_bloque=b.id")
    i_df = db_query("SELECT id, nombre FROM inquilinos")
    if u_df is not None and i_df is not None:
        with st.form("f_con", clear_on_submit=True):
            u_id = st.selectbox("Unidad", u_df['id'], format_func=lambda x: u_df[u_df['id']==x]['ref'].values[0])
            i_id = st.selectbox("Inquilino", i_df['id'], format_func=lambda x: i_df[i_df['id']==x]['nombre'].values[0])
            f_ini = st.date_input("Inicio", date.today())
            monto = st.text_input("Monto Alquiler", value=f_m(u_df[u_df['id']==u_id]['precio_alquiler'].values[0]))
            if st.form_submit_button("GRABAR"):
                cid = db_query("INSERT INTO contratos (id_inmueble, id_inquilino, fecha_inicio, monto_alquiler) VALUES (?,?,?,?)", (u_id, i_id, f_ini, cl(monto)), commit=True)
                db_query("INSERT INTO deudas (id_contrato, concepto, monto_debe) VALUES (?, 'Mes 1', ?)", (cid, cl(monto)), commit=True)
                st.success("Contrato grabado y primer cuota generada.")

elif menu == "💰 Cobranzas":
    st.header("Cobranzas y Recibos")
    deu = db_query("""
        SELECT d.id, inq.nombre as Inquilino, b.nombre as Edificio, i.tipo as Unidad, 
               d.concepto, d.monto_debe, d.monto_pago 
        FROM deudas d JOIN contratos c ON d.id_contrato=c.id 
        JOIN inmuebles i ON c.id_inmueble=i.id JOIN bloques b ON i.id_bloque=b.id
        JOIN inquilinos inq ON c.id_inquilino=inq.id WHERE d.pagado=0
    """)
    if deu is not None:
        for _, r in deu.iterrows():
            saldo = r['monto_debe'] - r['monto_pago']
            with st.expander(f"{r['Inquilino']} - {r['Unidad']} (Saldo: ${f_m(saldo)})"):
                pago_parcial = st.text_input("Importe a cobrar", value=f_m(saldo), key=f"in_{r['id']}")
                if st.button("Confirmar Cobro", key=f"btn_{r['id']}"):
                    nuevo_total = r['monto_pago'] + cl(pago_parcial)
                    esta_pagado = 1 if nuevo_total >= r['monto_debe'] else 0
                    db_query("UPDATE deudas SET monto_pago=?, pagado=?, fecha_pago=? WHERE id=?", (nuevo_total, esta_pagado, date.today(), r['id']), commit=True)
                    
                    st.subheader("📄 RECIBO DE PAGO")
                    recibo = f"""
                    --------------------------------------------------
                    NL INMOBILIARIA - COMPROBANTE DE PAGO
                    --------------------------------------------------
                    INMUEBLE: {r['Edificio']} | UNIDAD: {r['Unidad']}
                    INQUILINO: {r['Inquilino']}
                    CONCEPTO: {r['concepto']}
                    IMPORTE ABONADO: $ {pago_parcial}
                    SALDO PENDIENTE: $ {f_m(r['monto_debe'] - nuevo_total)}
                    FECHA: {date.today()}
                    --------------------------------------------------
                                    NL INMOBILIARIA
                    --------------------------------------------------
                    """
                    st.code(recibo)
                    if esta_pagado: st.success("Cuota cancelada totalmente.")
                    else: st.warning("Pago parcial registrado.")

elif menu == "⚙️ Maestros":
    st.header("Administración")
    t1, t2, t3, t4 = st.tabs(["🏢 Inmuebles", "🏠 Unidades", "👤 Inquilinos", "📋 Contratos"])
    
    with t1:
        with st.form("f_inm"):
            n = st.text_input("Nombre (Ej: Edificio Central)"); d = st.text_input("Dirección"); b = st.text_input("Barrio"); l = st.text_input("Localidad")
            if st.form_submit_button("Guardar Inmueble"):
                db_query("INSERT INTO bloques (nombre, direccion, barrio, localidad) VALUES (?,?,?,?)", (n, d, b, l), commit=True); st.rerun()
        st.dataframe(db_query("SELECT * FROM bloques"), use_container_width=True)

    with t4:
        st.subheader("Generación de Alquiler Mensual")
        c_activos = db_query("""
            SELECT c.id, inq.nombre, b.nombre as edif, i.tipo, c.monto_alquiler 
            FROM contratos c JOIN inquilinos inq ON c.id_inquilino=inq.id 
            JOIN inmuebles i ON c.id_inmueble=i.id JOIN bloques b ON i.id_bloque=b.id WHERE c.activo=1
        """)
        if not c_activos.empty:
            st.dataframe(c_activos)
            c_sel = st.selectbox("Seleccione contrato para generar Próximo Mes", c_activos['id'])
            mes_nombre = st.text_input("Concepto (Ej: Alquiler Marzo 2026)", "Alquiler")
            if st.button("⚡ GENERAR DEUDA"):
                monto_alq = c_activos[c_activos['id']==c_sel]['monto_alquiler'].values[0]
                db_query("INSERT INTO deudas (id_contrato, concepto, monto_debe) VALUES (?, ?, ?)", (c_sel, mes_nombre, monto_alq), commit=True)
                st.success("Deuda generada en Cobranzas.")
