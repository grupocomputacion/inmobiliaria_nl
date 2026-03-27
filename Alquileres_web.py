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
# 3. GENERADOR DE PDF (TEXTO LEGAL ÍNTEGRO V.5.3)
# ==========================================
def generar_pdf_v5(datos_u, datos_i, f_inicio, m_alq, m_dep, m_con):
    pdf = FPDF()
    pdf.add_page()
    
    # 1. Logo (Si existe)
    if os.path.exists("alquileres.jpg"):
        pdf.image("alquileres.jpg", 10, 8, 30)
    
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, 'CONTRATO DE LOCACION TEMPORARIA (3 MESES)', 0, 1, 'C')
    pdf.ln(5)
    
    pdf.set_font('Arial', '', 10)
    hoy = date.today()
    meses_nom = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
    
    # 2. TEXTO LEGAL EXACTO (Mapeado con tus puntos 2.a a 2.h)
    # Nota: Usamos 'B.' para evitar el error del símbolo de grado
    texto_legal = f"""Entre NL PROPIEDADES, CUIT 30-71884850-0 con domicilio en Av. Velez Sarsfield 745, B. Nueva Cordoba, Cordoba Capital, en adelante "EL LOCADOR" y por la otra parte {datos_i['nombre'].upper()}, DNI {datos_i['dni']}, con domicilio en {datos_i['procedencia'] or 'S/D'}, en adelante "EL LOCATARIO", se celebra el presente contrato sujeto a las siguientes clausulas:

1) OBJETO: Se alquila el inmueble ubicado en {datos_u['direccion'] or 'S/D'}, destinado a uso vivienda / comercial. Unidad: {datos_u['tipo']}.

2) PLAZO: El contrato tendra una duracion de TRES (3) MESES, iniciando el dia {f_inicio.strftime('%d/%m/%Y')}.

3) PRECIO: El valor del alquiler por mes, sera de $ {f_m(cl(m_alq))}.

4) GARANTIA: Se recibe la suma de $ {f_m(cl(m_dep))}, en concepto de Garantia, la misma sera reintegrada al finalizar el contrato, el locatario debera dar previo aviso de 15 dias por escrito de la discontinuidad del alquiler una vez finalicen los 3 meses. En caso de que el inmueble presentara algun desperfecto (rotura, pintura, artefactos danados, etc.) se utilizara el monto recibido para reparaciones. En caso de incumplimientos contractuales, el monto de la garantia quedara para el locador como resarcimiento.

5) GASTOS: Seran a cargo del locatario todos los servicios, tasas e impuestos que correspondan al uso del inmueble.

6) PROHIBICIONES: No se podra cambiar la titularidad del contrato ni subalquilar total o parcialmente el inmueble. No se aceptan mascotas, ni menores de edad.

7) FIRMA: La firma del presente contrato tiene un costo administrativo de $ {f_m(cl(m_con))}.

8) MORA: Ante mora del pago del alquiler mensual, EL LOCATARIO debera desalojar el inmueble habitado, en un plazo no maximo a 15 dias de corrido.

El locatario declara recibir el inmueble en buen estado y se compromete a devolverlo en iguales condiciones.

En prueba de conformidad, se firman dos ejemplares de un mismo tenor en la ciudad de Cordoba, a los {hoy.day} dias del mes de {meses_nom[hoy.month-1]} del año {hoy.year}.
"""
    # 3. Renderizado del texto (Limpiamos caracteres extraños para evitar el SyntaxError)
    clean_text = texto_legal.encode('latin-1', 'replace').decode('latin-1')
    pdf.multi_cell(0, 6, clean_text)
    pdf.ln(10)
    
    # 4. BLOQUE DE FIRMAS
    pdf.set_font('Arial', 'B', 10)
    pdf.cell(90, 5, 'LA LOCADORA - NL PROPIEDADES', 0, 0, 'L')
    pdf.cell(90, 5, 'EL LOCATARIO', 0, 1, 'R')
    
    pdf.set_font('Arial', '', 9)
    pdf.cell(90, 8, 'Firma: __________________________', 0, 0, 'L')
    pdf.cell(90, 8, 'Firma: __________________________', 0, 1, 'R')
    
    pdf.cell(90, 8, 'Aclaracion: NL PROPIEDADES', 0, 0, 'L')
    pdf.cell(90, 8, f"Aclaracion: {datos_i['nombre']}", 0, 1, 'R')
    
    pdf.cell(90, 8, 'DNI/CUIT: 30-71884850-0', 0, 0, 'L')
    pdf.cell(90, 8, f"DNI: {datos_i['dni']}", 0, 1, 'R')
    
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

# ==========================================
# 2. NUEVO CONTRATO + PDF (V.5.2 - CORREGIDO)
# ==========================================
elif menu == "📝 Nuevo Contrato":
    st.header("Formalización de Contrato y PDF")
    
    # Query con nombres explícitos para evitar KeyError
    u_df = db_query("""
        SELECT i.id, b.nombre || ' - ' || i.tipo as ref, b.direccion, b.barrio, b.localidad, 
               i.tipo, i.precio_alquiler, i.costo_contrato, i.deposito_base 
        FROM inmuebles i JOIN bloques b ON i.id_bloque=b.id
    """)
    i_df = db_query("SELECT * FROM inquilinos")
    
    if u_df is not None and i_df is not None and not u_df.empty:
        with st.form("f_contrato_v52"):
            col1, col2 = st.columns(2)
            uid = col1.selectbox("Unidad", u_df['id'], format_func=lambda x: u_df[u_df['id']==x]['ref'].values[0])
            iid = col2.selectbox("Inquilino", i_df['id'], format_func=lambda x: i_df[i_df['id']==x]['nombre'].values[0])
            
            # 1. Selector de Meses (Punto 1 solicitado)
            fini = col1.date_input("Fecha Inicio", date.today())
            meses = col2.number_input("Cantidad de Meses", min_value=1, max_value=60, value=3)
            
            sel_u = u_df[u_df['id'] == uid].iloc[0]
            
            # Montos con formato de miles
            ma = col1.text_input("Alquiler Mensual", f_m(sel_u['precio_alquiler']))
            md = col2.text_input("Depósito Garantía", f_m(sel_u['deposito_base']))
            mc = st.text_input("Gasto Administrativo / Contrato", f_m(sel_u['costo_contrato']))
            
            if st.form_submit_button("GRABAR Y GENERAR PDF"):
                # Calculamos vencimiento exacto para Disponibilidad
                f_vence = fini + timedelta(days=meses * 30)
                
                # Grabar Contrato
                cid = db_query("""INSERT INTO contratos (id_inmueble, id_inquilino, fecha_inicio, fecha_fin, monto_alquiler) 
                                 VALUES (?,?,?,?,?)""", (uid, iid, fini, f_vence, cl(ma)), commit=True)
                
                # Generar las 3 deudas iniciales
                db_query("INSERT INTO deudas (id_contrato, concepto, monto_debe) VALUES (?, 'Mes 1 Alquiler', ?)", (cid, cl(ma)), commit=True)
                db_query("INSERT INTO deudas (id_contrato, concepto, monto_debe) VALUES (?, 'Garantía/Depósito', ?)", (cid, cl(md)), commit=True)
                db_query("INSERT INTO deudas (id_contrato, concepto, monto_debe) VALUES (?, 'Gastos Administrativos', ?)", (cid, cl(mc)), commit=True)
                
                # Generar PDF con los datos validados
                try:
                    pdf_bytes = generar_pdf_v5(sel_u, i_df[i_df['id']==iid].iloc[0], fini, ma, md, mc)
                    st.session_state['pdf_ready'] = pdf_bytes
                    st.session_state['cid_last'] = cid
                    st.success(f"Contrato {cid} grabado. Vence el {f_vence.strftime('%d/%m/%Y')}")
                except Exception as e:
                    st.error(f"Error al generar PDF: {e}. Verifique que las columnas existan.")

        if 'pdf_ready' in st.session_state:
            st.write("---")
            st.download_button("📥 DESCARGAR CONTRATO PDF", st.session_state['pdf_ready'], f"Contrato_NL_{st.session_state['cid_last']}.pdf", "application/pdf")
    else:
        st.warning("Debe cargar Inmuebles, Unidades e Inquilinos en 'Maestros' primero.")


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

# ==========================================
# 6. MAESTROS (V.5.1 - GESTIÓN INTEGRAL)
# ==========================================
elif menu == "⚙️ Maestros":
    st.header("Administración de Base de Datos")
    t1, t2, t3, t4 = st.tabs(["🏢 Inmuebles", "🏠 Unidades", "👤 Inquilinos", "📋 Contratos"])

    # --- 1. INMUEBLES (EX BLOQUES) ---
    with t1:
        st.subheader("Edificios y Complejos")
        with st.expander("➕ Cargar Nuevo Inmueble"):
            with st.form("f_inm_alta", clear_on_submit=True):
                c1, c2 = st.columns(2)
                n = c1.text_input("Nombre del Edificio")
                d = c1.text_input("Dirección")
                b = c2.text_input("Barrio")
                l = c2.text_input("Localidad")
                if st.form_submit_button("Guardar Inmueble"):
                    db_query("INSERT INTO bloques (nombre, direccion, barrio, localidad) VALUES (?,?,?,?)", (n, d, b, l), commit=True)
                    st.rerun()
        
        df_inm = db_query("SELECT * FROM bloques")
        if df_inm is not None and not df_inm.empty:
            st.dataframe(df_inm, use_container_width=True, hide_index=True)
            st.write("---")
            sel_inm = st.selectbox("Seleccione Inmueble para EDITAR o BORRAR", df_inm['nombre'].tolist())
            dat_inm = df_inm[df_inm['nombre'] == sel_inm].iloc[0]
            
            with st.form("f_inm_edit"):
                c1, c2 = st.columns(2)
                en = c1.text_input("Editar Nombre", dat_inm['nombre'])
                ed = c1.text_input("Editar Dirección", dat_inm['direccion'])
                eb = c2.text_input("Editar Barrio", dat_inm['barrio'])
                el = c2.text_input("Editar Localidad", dat_inm['localidad'])
                col_b1, col_b2 = st.columns(2)
                if col_b1.form_submit_button("💾 Guardar Cambios"):
                    db_query("UPDATE bloques SET nombre=?, direccion=?, barrio=?, localidad=? WHERE id=?", (en, ed, eb, el, dat_inm['id']), commit=True)
                    st.rerun()
                if col_b2.form_submit_button("🗑️ ELIMINAR INMUEBLE"):
                    db_query(f"DELETE FROM bloques WHERE id={dat_inm['id']}", commit=True)
                    st.rerun()

    # --- 2. UNIDADES ---
    with t2:
        st.subheader("Gestión de Unidades / Departamentos")
        df_b_ref = db_query("SELECT id, nombre FROM bloques")
        if df_b_ref is not None and not df_b_ref.empty:
            with st.expander("➕ Cargar Nueva Unidad"):
                with st.form("f_u_alta", clear_on_submit=True):
                    bid = st.selectbox("Inmueble Perteneciente", df_b_ref['id'], format_func=lambda x: df_b_ref[df_b_ref['id']==x]['nombre'].values[0])
                    tipo = st.text_input("Descripción de Unidad (Ej: Depto 1A)")
                    c1, c2, c3 = st.columns(3)
                    p1 = c1.text_input("Alquiler Sugerido")
                    p2 = c2.text_input("Costo Contrato Sug.")
                    p3 = c3.text_input("Depósito Sugerido")
                    if st.form_submit_button("Crear Unidad"):
                        db_query("INSERT INTO inmuebles (id_bloque, tipo, precio_alquiler, costo_contrato, deposito_base) VALUES (?,?,?,?,?)", (bid, tipo, cl(p1), cl(p2), cl(p3)), commit=True)
                        st.rerun()
            
            df_uni = db_query("""SELECT i.id, b.nombre as Inmueble, i.tipo as Unidad, i.precio_alquiler, i.costo_contrato, i.deposito_base 
                                 FROM inmuebles i JOIN bloques b ON i.id_bloque = b.id""")
            if df_uni is not None and not df_uni.empty:
                st.dataframe(df_uni, use_container_width=True, hide_index=True)
                st.write("---")
                sel_u = st.selectbox("Seleccione Unidad para EDITAR o BORRAR", df_uni['Unidad'].tolist())
                u_curr = db_query(f"SELECT * FROM inmuebles WHERE tipo='{sel_u}'").iloc[0]
                
                with st.form("f_u_edit"):
                    c1, c2, c3 = st.columns(3)
                    en_tipo = st.text_input("Descripción", u_curr['tipo'])
                    en_p1 = c1.text_input("Alquiler", f_m(u_curr['precio_alquiler']))
                    en_p2 = c2.text_input("Contrato", f_m(u_curr['costo_contrato']))
                    en_p3 = c3.text_input("Depósito", f_m(u_curr['deposito_base']))
                    col_u1, col_u2 = st.columns(2)
                    if col_u1.form_submit_button("💾 Actualizar Unidad"):
                        db_query("UPDATE inmuebles SET tipo=?, precio_alquiler=?, costo_contrato=?, deposito_base=? WHERE id=?", (en_tipo, cl(en_p1), cl(en_p2), cl(en_p3), u_curr['id']), commit=True)
                        st.rerun()
                    if col_u2.form_submit_button("🗑️ Eliminar Unidad"):
                        db_query(f"DELETE FROM inmuebles WHERE id={u_curr['id']}", commit=True)
                        st.rerun()

    # --- 3. INQUILINOS ---
    with t3:
        st.subheader("Registro de Inquilinos")
        with st.expander("➕ Cargar Nuevo Inquilino"):
            with st.form("f_inq_alta", clear_on_submit=True):
                c1, c2 = st.columns(2)
                n = c1.text_input("Nombre y Apellido"); d = c1.text_input("DNI / CUIT"); c = c1.text_input("WhatsApp")
                p = c2.text_input("Procedencia"); g = c2.text_input("Grupo / Ref"); e = c2.text_input("Emergencia")
                if st.form_submit_button("Guardar Inquilino"):
                    db_query("INSERT INTO inquilinos (nombre, dni, celular, procedencia, grupo, emergencia) VALUES (?,?,?,?,?,?)", (n, d, c, p, g, e), commit=True)
                    st.rerun()
        
        df_inq = db_query("SELECT * FROM inquilinos")
        if df_inq is not None and not df_inq.empty:
            st.dataframe(df_inq, use_container_width=True, hide_index=True)
            sel_inq = st.selectbox("Seleccione Inquilino para EDITAR o BORRAR", df_inq['nombre'].tolist())
            i_dat = df_inq[df_inq['nombre'] == sel_inq].iloc[0]
            with st.form("f_inq_edit"):
                c1, c2 = st.columns(2)
                en_n = c1.text_input("Nombre", i_dat['nombre']); en_d = c1.text_input("DNI", i_dat['dni'])
                en_c = c1.text_input("WhatsApp", i_dat['celular']); en_p = c2.text_input("Procedencia", i_dat['procedencia'])
                en_g = c2.text_input("Grupo", i_dat['grupo']); en_e = c2.text_input("Emergencia", i_dat['emergencia'])
                col_i1, col_i2 = st.columns(2)
                if col_i1.form_submit_button("💾 Actualizar"):
                    db_query("UPDATE inquilinos SET nombre=?, dni=?, celular=?, procedencia=?, grupo=?, emergencia=? WHERE id=?", (en_n, en_d, en_c, en_p, en_g, en_e, i_dat['id']), commit=True)
                    st.rerun()
                if col_i2.form_submit_button("🗑️ Borrar Inquilino"):
                    db_query(f"DELETE FROM inquilinos WHERE id={i_dat['id']}", commit=True); st.rerun()

    # --- 4. CONTRATOS VIVOS ---
    with t4:
        st.subheader("Contratos Vigentes")
        df_cont = db_query("""SELECT c.id, b.nombre as Inmueble, i.tipo as Unidad, inq.nombre as Inquilino, c.fecha_inicio, c.monto_alquiler 
                             FROM contratos c JOIN inmuebles i ON c.id_inmueble = i.id 
                             JOIN bloques b ON i.id_bloque = b.id JOIN inquilinos inq ON c.id_inquilino = inq.id WHERE c.activo = 1""")
        if df_cont is not None and not df_cont.empty:
            st.dataframe(df_cont, use_container_width=True, hide_index=True)
            sel_c = st.selectbox("Seleccione ID de Contrato para DAR DE BAJA", df_cont['id'].tolist())
            if st.button("🚨 ELIMINAR CONTRATO Y SUS DEUDAS"):
                db_query(f"DELETE FROM contratos WHERE id={sel_c}", commit=True)
                db_query(f"DELETE FROM deudas WHERE id_contrato={sel_c}", commit=True)
                st.rerun()
        else:
            st.info("No hay contratos activos registrados.")
