import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, date, timedelta
import os
import io
from fpdf import FPDF

# ==========================================
# 1. CONFIGURACIÓN E IDENTIDAD (V.5.0)
# ==========================================
st.set_page_config(page_title="NL INMOBILIARIA - V.5.0", layout="wide")
st.cache_data.clear()

st.markdown("""
    <style>
    .stButton>button { background-color: #D4AF37; color: black; font-weight: bold; width: 100%; border-radius: 5px; }
    h1, h2, h3, h4 { color: #D4AF37; }
    [data-testid="stSidebar"] { background-color: #111; border-right: 1px solid #D4AF37; }
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 2. MOTOR DE DATOS (ESTRUCTURA FINAL)
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

def inicializar_todo():
    db_query("""CREATE TABLE IF NOT EXISTS bloques (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                nombre TEXT, direccion TEXT, barrio TEXT, localidad TEXT)""", commit=True)
    db_query("""CREATE TABLE IF NOT EXISTS inquilinos (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                nombre TEXT, dni TEXT, celular TEXT, emergencia TEXT, procedencia TEXT, grupo TEXT)""", commit=True)
    db_query("""CREATE TABLE IF NOT EXISTS inmuebles (id INTEGER PRIMARY KEY AUTOINCREMENT, id_bloque INTEGER, 
                tipo TEXT, precio_alquiler INTEGER, costo_contrato INTEGER, deposito_base INTEGER)""", commit=True)
    db_query("""CREATE TABLE IF NOT EXISTS contratos (id INTEGER PRIMARY KEY AUTOINCREMENT, id_inmueble INTEGER, 
                id_inquilino INTEGER, fecha_inicio DATE, fecha_fin DATE, monto_alquiler INTEGER, activo INTEGER DEFAULT 1)""", commit=True)
    db_query("""CREATE TABLE IF NOT EXISTS deudas (id INTEGER PRIMARY KEY AUTOINCREMENT, id_contrato INTEGER, 
                concepto TEXT, monto_debe INTEGER, monto_pago INTEGER DEFAULT 0, pagado INTEGER DEFAULT 0, fecha_pago DATE)""", commit=True)

inicializar_todo()

def cl(t): return int(str(t).replace('$', '').replace('.', '').replace(',', '').strip() or 0)
def f_m(v): return f"{int(v or 0):,}".replace(",", ".")

# ==========================================
# 3. GENERADOR DE PDF (TEXTO LEGAL EXACTO)
# ==========================================
def generar_pdf_v5(datos_u, datos_i, f_inicio, m_alq, m_dep, m_con):
    pdf = FPDF()
    pdf.add_page()
    if os.path.exists("alquileres.jpg"): pdf.image("alquileres.jpg", 10, 8, 30)
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, 'CONTRATO DE LOCACION TEMPORARIA (3 MESES)', 0, 1, 'C')
    pdf.ln(5)
    pdf.set_font('Arial', '', 10)
    hoy = date.today()
    meses_nom = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
    
    texto = f"""Entre NL PROPIEDADES, CUIT 30-71884850-0 con domicilio en Av. Velez Sarsfield 745, B. Nueva Cordoba, Cordoba Capital, en adelante "EL LOCADOR" y por la otra parte {datos_i['nombre'].upper()}, DNI {datos_i['dni']}, con domicilio en {datos_i['procedencia'] or 'S/D'}, en adelante "EL LOCATARIO", se celebra el presente contrato sujeto a las siguientes clausulas:

1) OBJETO: Se alquila el inmueble ubicado en {datos_u['direccion'] or 'S/D'}, destinado a uso vivienda / comercial. Unidad: {datos_u['tipo']}.

2) PLAZO: El contrato tendra una duracion de TRES (3) MESES, iniciando el dia {f_inicio.strftime('%d/%m/%Y')}.

3) PRECIO: El valor del alquiler por mes, sera de $ {f_m(cl(m_alq))}.

4) GARANTIA: Se recibe la suma de $ {f_m(cl(m_dep))}, en concepto de Garantia...

7) FIRMA: La firma del presente contrato tiene un costo administrativo de $ {f_m(cl(m_con))}.

En prueba de conformidad, se firman dos ejemplares en Cordoba, a los {hoy.day} dias del mes de {meses_nom[hoy.month-1]} del año {hoy.year}.
"""
    pdf.multi_cell(0, 6, texto.encode('latin-1', 'replace').decode('latin-1'))
    pdf.ln(10)
    pdf.cell(90, 5, 'LA LOCADORA - NL PROPIEDADES', 0, 0, 'L')
    pdf.cell(90, 5, 'EL LOCATARIO', 0, 1, 'R')
    pdf.cell(90, 8, 'Aclaracion: NL PROPIEDADES', 0, 0, 'L')
    pdf.cell(90, 8, f"Aclaracion: {datos_i['nombre']}", 0, 1, 'R')
    return pdf.output(dest='S').encode('latin-1')

# ==========================================
# 4. BARRA LATERAL
# ==========================================
with st.sidebar:
    if os.path.exists("alquileres.jpg"): st.image("alquileres.jpg", use_container_width=True)
    st.info("🚀 SISTEMA NL V.5.0")
    menu = st.radio("MENÚ:", ["🏠 Inventario", "📝 Nuevo Contrato", "💰 Cobranzas", "🚨 Morosos", "📊 Caja", "⚙️ Maestros"])
    if st.button("🚨 RESET TOTAL (LIMPIAR ERRORES)"):
        if os.path.exists('datos_alquileres.db'): os.remove('datos_alquileres.db')
        st.rerun()

# ==========================================
# 5. SECCIONES
# ==========================================

if menu == "🏠 Inventario":
    st.header("Inventario y Disponibilidad")
    df = db_query("""SELECT b.nombre as Inmueble, i.tipo as Unidad, i.precio_alquiler as Alquiler, 
                     i.costo_contrato as Contrato, i.deposito_base as Deposito,
                     CASE WHEN c.activo = 1 THEN '🔴 OCUPADO' ELSE '🟢 LIBRE' END as Estado
                     FROM inmuebles i JOIN bloques b ON i.id_bloque = b.id
                     LEFT JOIN contratos c ON i.id = c.id_inmueble AND c.activo = 1""")
    if df is not None and not df.empty:
        c1, c2 = st.columns(2)
        c1.metric("Unidades Libres", len(df[df['Estado'] == '🟢 LIBRE']))
        c2.metric("Total Unidades", len(df))
        for col in ['Alquiler', 'Contrato', 'Deposito']: df[col] = df[col].apply(f_m)
        st.dataframe(df, use_container_width=True, hide_index=True)

elif menu == "📝 Nuevo Contrato":
    st.header("Alta de Contrato")
    u_df = db_query("SELECT i.id, b.nombre || ' - ' || i.tipo as ref, b.direccion, i.precio_alquiler, i.costo_contrato, i.deposito_base FROM inmuebles i JOIN bloques b ON i.id_bloque=b.id")
    i_df = db_query("SELECT * FROM inquilinos")
    if u_df is not None and not u_df.empty:
        with st.form("f_con"):
            uid = st.selectbox("Unidad", u_df['id'], format_func=lambda x: u_df[u_df['id']==x]['ref'].values[0])
            iid = st.selectbox("Inquilino", i_df['id'], format_func=lambda x: i_df[i_df['id']==x]['nombre'].values[0])
            fini = st.date_input("Inicio", date.today())
            sel_u = u_df[u_df['id']==uid].iloc[0]
            ma = st.text_input("Alquiler", f_m(sel_u['precio_alquiler']))
            md = st.text_input("Depósito", f_m(sel_u['deposito_base']))
            mc = st.text_input("Contrato", f_m(sel_u['costo_contrato']))
            if st.form_submit_button("GRABAR Y GENERAR PDF"):
                cid = db_query("INSERT INTO contratos (id_inmueble, id_inquilino, fecha_inicio, monto_alquiler) VALUES (?,?,?,?)", (uid, iid, fini, cl(ma)), commit=True)
                db_query("INSERT INTO deudas (id_contrato, concepto, monto_debe) VALUES (?, 'Mes 1', ?)", (cid, cl(ma)), commit=True)
                pdf = generar_pdf_v5(sel_u, i_df[i_df['id']==iid].iloc[0], fini, ma, md, mc)
                st.session_state['pdf'] = pdf
                st.success("Contrato grabado.")
        if 'pdf' in st.session_state: st.download_button("📥 DESCARGAR PDF", st.session_state['pdf'], "Contrato.pdf")

elif menu == "💰 Cobranzas":
    st.header("Cobranzas")
    deu = db_query("SELECT d.id, inq.nombre, i.tipo, d.concepto, d.monto_debe FROM deudas d JOIN contratos c ON d.id_contrato=c.id JOIN inmuebles i ON c.id_inmueble=i.id JOIN inquilinos inq ON c.id_inquilino=inq.id WHERE d.pagado=0")
    if deu is not None:
        for _, r in deu.iterrows():
            with st.expander(f"{r['nombre']} - {r['tipo']} (${f_m(r['monto_debe'])})"):
                if st.button("Confirmar Pago", key=f"b{r['id']}"):
                    db_query("UPDATE deudas SET pagado=1, fecha_pago=?, monto_pago=? WHERE id=?", (date.today(), r['monto_debe'], r['id']), commit=True); st.rerun()

elif menu == "🚨 Morosos":
    st.header("Morosos")
    mora = db_query("SELECT inq.nombre, d.monto_debe FROM deudas d JOIN contratos c ON d.id_contrato=c.id JOIN inquilinos inq ON c.id_inquilino=inq.id WHERE d.pagado=0")
    if mora is not None: st.table(mora)

elif menu == "📊 Caja":
    st.header("Caja Mensual")
    df_c = db_query("SELECT fecha_pago, concepto, monto_pago FROM deudas WHERE pagado=1")
    if df_c is not None: st.dataframe(df_c)

elif menu == "⚙️ Maestros":
    t1, t2, t3, t4 = st.tabs(["🏢 Inmuebles", "🏠 Unidades", "👤 Inquilinos", "📋 Contratos"])
    with t1:
        with st.form("fi"):
            n = st.text_input("Nombre"); d = st.text_input("Dirección"); b = st.text_input("Barrio"); l = st.text_input("Localidad")
            if st.form_submit_button("Guardar Inmueble"):
                db_query("INSERT INTO bloques (nombre, direccion, barrio, localidad) VALUES (?,?,?,?)", (n, d, b, l), commit=True); st.rerun()
        df_b = db_query("SELECT * FROM bloques")
        if df_b is not None:
            st.dataframe(df_b, use_container_width=True)
            sel = st.selectbox("Editar Inmueble", df_b['nombre'].tolist())
            dat = df_b[df_b['nombre']==sel].iloc[0]
            with st.form("fe"):
                en = st.text_input("Nombre", dat['nombre']); ed = st.text_input("Dirección", dat['direccion'])
                if st.form_submit_button("Actualizar"):
                    db_query("UPDATE bloques SET nombre=?, direccion=? WHERE id=?", (en, ed, dat['id']), commit=True); st.rerun()
                if st.form_submit_button("Eliminar"):
                    db_query(f"DELETE FROM bloques WHERE id={dat['id']}", commit=True); st.rerun()
    with t2:
        bls = db_query("SELECT * FROM bloques")
        if bls is not None:
            with st.form("fu"):
                bid = st.selectbox("Inmueble", bls['id'], format_func=lambda x: bls[bls['id']==x]['nombre'].values[0])
                ut = st.text_input("Unidad"); p1 = st.text_input("Alquiler"); p2 = st.text_input("Contrato"); p3 = st.text_input("Depósito")
                if st.form_submit_button("Crear"):
                    db_query("INSERT INTO inmuebles (id_bloque, tipo, precio_alquiler, costo_contrato, deposito_base) VALUES (?,?,?,?,?)", (bid, ut, cl(p1), cl(p2), cl(p3)), commit=True); st.rerun()
