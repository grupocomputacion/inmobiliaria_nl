import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, date, timedelta
import os
import io
from fpdf import FPDF # <-- NUEVA LIBRERÍA

# ==========================================
# 1. IDENTIDAD Y CONFIGURACIÓN (V.4.1)
# ==========================================
st.set_page_config(page_title="NL INMOBILIARIA - V.4.1", layout="wide")
st.cache_data.clear()

st.markdown("""
    <style>
    .stButton>button { background-color: #D4AF37; color: black; font-weight: bold; width: 100%; border-radius: 5px; }
    h1, h2, h3, h4 { color: #D4AF37; }
    [data-testid="stSidebar"] { background-color: #111; border-right: 1px solid #D4AF37; }
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 2. MOTOR DE DATOS
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
        st.error(f"Error de base de datos: {e}")
        return None

# Funciones de formato
def cl(t): return int(str(t).replace('$', '').replace('.', '').replace(',', '').strip() or 0)
def f_m(v): return f"{int(v or 0):,}".replace(",", ".")

# ==========================================
# 3. GENERADOR DE PDF PROFESIONAL
# ==========================================
def generar_pdf_contrato(datos_u, datos_i, f_inicio, m_alq, m_dep, m_con):
    class PDF(FPDF):
        def header(self):
            if os.path.exists("alquileres.jpg"):
                self.image("alquileres.jpg", 10, 8, 33)
            self.set_font('Arial', 'B', 15)
            self.cell(80)
            self.cell(30, 10, 'CONTRATO DE LOCACIÓN TEMPORARIA', 0, 0, 'C')
            self.ln(20)

    # Configuración del PDF
    pdf = PDF()
    pdf.add_page()
    pdf.set_font('Arial', '', 11)
    
    # Fechas y Nombres de Meses
    hoy = date.today()
    meses_nom = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "deziembre"]
    f_vence = f_inicio + timedelta(days=90) # 3 meses aprox

    # TEXTO LEGAL CON REEMPLAZO DINÁMICO (Mapeado de tus puntos 2.a a 2.h)
    texto = f"""Entre NL PROPIEDADES, CUIT 30-71884850-0 con domicilio en Av. Vélez Sarsfield 745, B° Nueva Córdoba, Córdoba Capital, en adelante “EL LOCADOR” y por la otra parte {datos_i['nombre'].upper()}, DNI {datos_i['dni']}, con domicilio en {datos_i['procedencia']}, en adelante “EL LOCATARIO”, se celebra el presente contrato sujeto a las siguientes cláusulas:

1) OBJETO: Se alquila el inmueble ubicado en {datos_u['direccion']}, {datos_u['barrio']}, {datos_u['localidad']}, destinado a uso vivienda / comercial. Unidad: {datos_u['tipo']}.

2) PLAZO: El contrato tendrá una duración de TRES (3) MESES, iniciando el día {f_inicio.strftime('%d/%m/%Y')}.

3) PRECIO: El valor del alquiler por mes, será de $ {f_m(cl(m_alq))}.

4) GARANTÍA: Se recibe la suma de $ {f_m(cl(m_dep))}, en concepto de Garantía, la misma será reintegrada al finalizar el contrato, el locatario deberá dar previo aviso de 15 días por escrito de la discontinuidad del alquiler una vez finalicen los 3 meses. . En caso de que el inmueble presentara algún desperfecto (rotura, pintura, artefactos dañados, etc.) se utilizará el monto recibido para reparaciones. En caso de incumplimientos contractuales, el monto de la garantía quedará para el locador como resarcimiento.

5) GASTOS: Serán a cargo del locatario todos los servicios, tasas e impuestos que correspondan al uso del inmueble.

6) PROHIBICIONES: No se podrá cambiar la titularidad del contrato ni subalquilar total o parcialmente el inmueble. No se aceptan mascotas, ni menores de edad.

7) FIRMA: La firma del presente contrato tiene un costo administrativo de $ {f_m(cl(m_con))}.

8) MORA: Ante mora del pago del alquiler mensual, EL LOCATARIO deberá desalojar el inmueble habitado, en un plazo no máximo a 15 días de corrido.

El locatario declara recibir el inmueble en buen estado y se compromete a devolverlo en iguales condiciones.

En prueba de conformidad, se firman dos ejemplares de un mismo tenor en la ciudad de Córdoba, a los {hoy.day} días del mes de {meses_nom[hoy.month-1]} del año {hoy.year}.
"""
    # Escribimos el texto legal
    pdf.multi_cell(0, 7, texto)
    pdf.ln(15)

    # SECCIÓN DE FIRMAS (Punto 2 y Firmante Inmobiliaria)
    pdf.set_font('Arial', 'B', 11)
    
    # Líneas de firma
    pdf.cell(90, 10, '_______________________________', 0, 0, 'L')
    pdf.cell(90, 10, '_______________________________', 0, 1, 'R')
    
    # Títulos
    pdf.cell(90, 7, 'LA LOCADORA - NL PROPIEDADES', 0, 0, 'L')
    pdf.cell(90, 7, 'EL LOCATARIO', 0, 1, 'R')
    
    pdf.set_font('Arial', '', 10)
    
    # Datos de los firmantes
    pdf.cell(90, 5, 'Firma: __________________________', 0, 0, 'L')
    pdf.cell(90, 5, f"Firma: __________________________", 0, 1, 'R')
    
    pdf.cell(90, 5, 'Aclaración: NL PROPIEDADES', 0, 0, 'L')
    pdf.cell(90, 5, f"Aclaración: {datos_i['nombre']}", 0, 1, 'R')
    
    pdf.cell(90, 5, 'DNI/CUIT: 30-71884850-0', 0, 0, 'L')
    pdf.cell(90, 5, f"DNI: {datos_i['dni']}", 0, 1, 'R')

    # Retornamos el PDF como binario
    return pdf.output(dest='S').encode('latin-1')

# ==========================================
# 4. BARRA LATERAL (MENÚ)
# ==========================================
with st.sidebar:
    if os.path.exists("alquileres.jpg"): st.image("alquileres.jpg", use_container_width=True)
    st.info("🚀 V.4.1 - PDF NATIVO")
    menu = st.radio("MENÚ:", ["🏠 Inventario", "📝 Nuevo Contrato", "💰 Cobranzas", "📊 Caja", "⚙️ Maestros"])

# ==========================================
# 5. LÓGICA DE SECCIONES
# ==========================================

# --- 1. INVENTARIO (Simplificado para debug) ---
if menu == "🏠 Inventario": st.header("Inventario de Unidades"); st.write(db_query("SELECT i.id, b.nombre, i.tipo, i.precio_alquiler FROM inmuebles i JOIN bloques b ON i.id_bloque = b.id"))

# --- 2. NUEVO CONTRATO (FULL AUTOMÁTICO + PDF) ---
elif menu == "📝 Nuevo Contrato":
    st.header("Formalización de Contrato Legal")
    
    u_df = db_query("SELECT i.id, b.nombre || ' - ' || i.tipo as ref, b.direccion, b.barrio, b.localidad, i.tipo, i.precio_alquiler, i.costo_contrato, i.deposito_base FROM inmuebles i JOIN bloques b ON i.id_bloque=b.id")
    i_df = db_query("SELECT * FROM inquilinos")
    
    if u_df is not None and i_df is not None and not u_df.empty and not i_df.empty:
        # Usamos Session State para persistir el PDF generado
        if 'pdf_blob' not in st.session_state: st.session_state['pdf_blob'] = None
        if 'p_cid' not in st.session_state: st.session_state['p_cid'] = None

        with st.form("f_contrato_legal_full"):
            u_id = st.selectbox("Unidad", u_df['id'], format_func=lambda x: u_df[u_df['id']==x]['ref'].values[0])
            i_id = st.selectbox("Inquilino", i_df['id'], format_func=lambda x: i_df[i_df['id']==x]['nombre'].values[0])
            f_ini = st.date_input("Inicio Contrato", date.today())
            
            u_sel = u_df[u_df['id'] == u_id].iloc[0]
            m_alq = st.text_input("Alquiler Mensual", value=f_m(u_sel['precio_alquiler']))
            m_dep = st.text_input("Monto Depósito / Garantía", value=f_m(u_sel['deposito_base']))
            m_con = st.text_input("Gastos Administrativos", value=f_m(u_sel['costo_contrato']))
            
            st.warning("⚠️ Se generarán 3 deudas: Mes 1, Depósito y Gasto Contrato.")
            btn_generar = st.form_submit_button("📝 GENERAR CONTRATO LEGAL (PDF)")
            
            if btn_generar:
                # 1. Guardar Contrato y Generar las 3 Deudas (Punto 1 Solucionado)
                f_vence = f_ini + timedelta(days=90) # 3 meses aprox
                cid = db_query("INSERT INTO contratos (id_inmueble, id_inquilino, fecha_inicio, fecha_fin, monto_alquiler) VALUES (?,?,?,?,?)", 
                               (u_id, i_id, f_ini, f_vence, cl(m_alq)), commit=True)
                
                db_query("INSERT INTO deudas (id_contrato, concepto, monto_debe) VALUES (?, 'Mes 1 Alquiler', ?)", (cid, cl(m_alq)), commit=True)
                db_query("INSERT INTO deudas (id_contrato, concepto, monto_debe) VALUES (?, 'Depósito en Garantía', ?)", (cid, cl(m_dep)), commit=True)
                db_query("INSERT INTO deudas (id_contrato, concepto, monto_debe) VALUES (?, 'Gasto Contrato', ?)", (cid, cl(m_con)), commit=True)
                
                # 2. Generar el PDF binario (Punto 2 Solucionado)
                inquilino_sel = i_df[i_df['id'] == i_id].iloc[0]
                pdf_bin = generar_pdf_contrato(u_sel, inquilino_sel, f_ini, m_alq, m_dep, m_con)
                
                # Guardamos en Session State para que no se borre al hacer clic en descargar
                st.session_state['pdf_blob'] = pdf_bin
                st.session_state['p_cid'] = cid
                st.success(f"Contrato {cid} cargado y PDF generado.")

        # Botón de Descarga (aparece fuera del form si el PDF existe)
        if st.session_state['pdf_blob'] is not None:
            st.write("---")
            st.subheader("🎉 ¡Contrato Listo!")
            st.download_button(
                label="📥 Descargar Contrato PDF Firmado",
                data=st.session_state['pdf_blob'],
                file_name=f"Contrato_NL_{st.session_state['p_cid']}.pdf",
                mime="application/pdf"
            )

    else: st.error("Cargue datos en Maestros.")

    
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

# ==========================================
# 6. MAESTROS (V.2.9 - ABM TOTAL + GEN. MASIVA)
# ==========================================
elif menu == "⚙️ Maestros":
    st.header("Administración y Configuración del Sistema")
    t1, t2, t3, t4 = st.tabs(["🏢 Inmuebles", "🏠 Unidades", "👤 Inquilinos", "📋 Contratos"])
    
    # --- PESTAÑA 1: INMUEBLES (Edificios/Complejos) ---
    with t1:
        st.subheader("Gestión de Inmuebles")
        with st.expander("➕ Alta de Inmueble"):
            with st.form("f_inm_alta", clear_on_submit=True):
                c1, c2 = st.columns(2)
                n = c1.text_input("Nombre (Ej: Edificio Central)")
                d = c1.text_input("Dirección")
                b = c2.text_input("Barrio")
                l = c2.text_input("Localidad")
                if st.form_submit_button("Guardar"):
                    db_query("INSERT INTO bloques (nombre, direccion, barrio, localidad) VALUES (?,?,?,?)", (n, d, b, l), commit=True); st.rerun()
        
        df_inm = db_query("SELECT * FROM bloques")
        if not df_inm.empty:
            st.dataframe(df_inm, use_container_width=True, hide_index=True)
            sel_inm = st.selectbox("Seleccione Inmueble para EDITAR o BORRAR", df_inm['nombre'].tolist())
            dat_inm = df_inm[df_inm['nombre'] == sel_inm].iloc[0]
            with st.form("f_inm_edit"):
                en = st.text_input("Nombre", dat_inm['nombre'])
                ed = st.text_input("Dirección", dat_inm['direccion'])
                eb = st.text_input("Barrio", dat_inm['barrio'])
                el = st.text_input("Localidad", dat_inm['localidad'])
                c_in1, c_in2 = st.columns(2)
                if c_in1.form_submit_button("💾 Guardar Cambios"):
                    db_query("UPDATE bloques SET nombre=?, direccion=?, barrio=?, localidad=? WHERE id=?", (en, ed, eb, el, dat_inm['id']), commit=True); st.rerun()
                if c_in2.form_submit_button("🗑️ ELIMINAR INMUEBLE"):
                    db_query(f"DELETE FROM bloques WHERE id={dat_inm['id']}", commit=True); st.rerun()

    # --- PESTAÑA 2: UNIDADES ---
# --- PESTAÑA 2: UNIDADES (V.3.0 - FULL EDIT) ---
    with t2:
        st.subheader("Gestión Integral de Unidades")
        bls = db_query("SELECT id, nombre FROM bloques")
        
        if not bls.empty:
            # --- ALTA DE UNIDAD ---
            with st.expander("➕ Cargar Nueva Unidad"):
                with st.form("f_u_alta", clear_on_submit=True):
                    bid = st.selectbox("Inmueble", bls['id'], format_func=lambda x: bls[bls['id']==x]['nombre'].values[0])
                    desc = st.text_input("Descripción (Ej: Piso 1 Dpto A)")
                    c_a1, c_a2, c_a3 = st.columns(3)
                    p1 = c_a1.text_input("Alquiler Sugerido")
                    p2 = c_a2.text_input("Gasto Contrato Sug.")
                    p3 = c_a3.text_input("Depósito Sugerido")
                    if st.form_submit_button("Crear Unidad"):
                        db_query("INSERT INTO inmuebles (id_bloque, tipo, precio_alquiler, costo_contrato, deposito_base) VALUES (?,?,?,?,?)", 
                                 (bid, desc, cl(p1), cl(p2), cl(p3)), commit=True)
                        st.success("Unidad creada correctamente."); st.rerun()
            
            # --- TABLA DE CONSULTA ---
            df_uni = db_query("""
                SELECT i.id, b.nombre as Inmueble, i.tipo as Unidad, 
                       i.precio_alquiler as Alquiler, i.costo_contrato as Contrato, i.deposito_base as Deposito
                FROM inmuebles i JOIN bloques b ON i.id_bloque=b.id
            """)
            
            if not df_uni.empty:
                # Formateamos los miles para la tabla
                df_disp = df_uni.copy()
                for col in ['Alquiler', 'Contrato', 'Deposito']:
                    df_disp[col] = df_disp[col].apply(f_m)
                
                st.dataframe(df_disp, use_container_width=True, hide_index=True)
                
                st.write("---")
                # --- EDICIÓN Y ELIMINACIÓN ---
                st.subheader("📝 Editar o Eliminar Unidad")
                sel_u_nom = st.selectbox("Seleccione Unidad para modificar", df_uni['Unidad'].tolist())
                # Traemos los datos actuales de la base
                u_curr = db_query(f"SELECT * FROM inmuebles WHERE tipo=?", (sel_u_nom,)).iloc[0]
                
                with st.form("f_u_edit"):
                    ed_desc = st.text_input("Descripción / Nombre", u_curr['tipo'])
                    c_ed1, c_ed2, c_ed3 = st.columns(3)
                    ed_alq = c_ed1.text_input("Alquiler Sugerido", value=f_m(u_curr['precio_alquiler']))
                    ed_con = c_ed2.text_input("Gasto Contrato", value=f_m(u_curr['costo_contrato']))
                    ed_dep = c_ed3.text_input("Depósito", value=f_m(u_curr['deposito_base']))
                    
                    col_btn1, col_btn2 = st.columns(2)
                    if col_btn1.form_submit_button("💾 GUARDAR CAMBIOS"):
                        db_query("""UPDATE inmuebles SET tipo=?, precio_alquiler=?, costo_contrato=?, deposito_base=? 
                                    WHERE id=?""", (ed_desc, cl(ed_alq), cl(ed_con), cl(ed_dep), u_curr['id']), commit=True)
                        st.success("Unidad actualizada correctamente."); st.rerun()
                    
                    if col_btn2.form_submit_button("🗑️ ELIMINAR UNIDAD"):
                        db_query(f"DELETE FROM inmuebles WHERE id={u_curr['id']}", commit=True)
                        st.warning("Unidad eliminada."); st.rerun()
        else:
            st.warning("Debe cargar al menos un Inmueble antes de crear Unidades.")

    # --- PESTAÑA 3: INQUILINOS ---
    with t3:
        st.subheader("Gestión de Inquilinos")
        with st.expander("➕ Alta de Inquilino"):
            with st.form("f_i_alta", clear_on_submit=True):
                c1, c2 = st.columns(2)
                in_n = c1.text_input("Nombre"); in_d = c1.text_input("DNI/CUIT"); in_c = c1.text_input("Celular")
                in_p = c2.text_input("Procedencia"); in_g = c2.text_input("Grupo"); in_e = c2.text_input("Emergencia")
                if st.form_submit_button("Guardar Inquilino"):
                    db_query("INSERT INTO inquilinos (nombre, dni, celular, procedencia, grupo, emergencia) VALUES (?,?,?,?,?,?)", (in_n, in_d, in_c, in_p, in_g, in_e), commit=True); st.rerun()
        
        df_inq = db_query("SELECT * FROM inquilinos")
        if not df_inq.empty:
            st.dataframe(df_inq, use_container_width=True, hide_index=True)
            sel_i = st.selectbox("Seleccione Inquilino para EDITAR/BORRAR", df_inq['nombre'].tolist())
            i_dat = df_inq[df_inq['nombre'] == sel_i].iloc[0]
            with st.form("f_i_edit"):
                en_n = st.text_input("Nombre", i_dat['nombre']); en_d = st.text_input("DNI", i_dat['dni'])
                en_c = st.text_input("Celular", i_dat['celular']); en_e = st.text_input("Emergencia", i_dat['emergencia'])
                if st.form_submit_button("💾 Actualizar Datos"):
                    db_query("UPDATE inquilinos SET nombre=?, dni=?, celular=?, emergencia=? WHERE id=?", (en_n, en_d, en_c, en_e, i_dat['id']), commit=True); st.rerun()
                if st.form_submit_button("🗑️ Borrar Inquilino"):
                    db_query(f"DELETE FROM inquilinos WHERE id={i_dat['id']}", commit=True); st.rerun()

    # --- PESTAÑA 4: CONTRATOS Y GENERACIÓN MASIVA ---
    with t4:
        st.subheader("Gestión de Contratos y Generación de Deuda")
        df_cont = db_query("""
            SELECT c.id, b.nombre as Inmueble, i.tipo as Unidad, inq.nombre as Inquilino, c.monto_alquiler 
            FROM contratos c JOIN inmuebles i ON c.id_inmueble=i.id 
            JOIN bloques b ON i.id_bloque=b.id JOIN inquilinos inq ON c.id_inquilino=inq.id WHERE c.activo=1
        """)
        
        if not df_cont.empty:
            st.dataframe(df_cont, use_container_width=True, hide_index=True)
            
            st.write("---")
            st.subheader("⚡ Generar Deuda de Alquiler")
            col_g1, col_g2 = st.columns(2)
            mes_txt = col_g1.text_input("Concepto", f"Alquiler {datetime.now().strftime('%B %Y')}")
            filtro_inm = col_g2.selectbox("Filtrar por Inmueble (Opcional)", ["TODOS"] + df_cont['Inmueble'].unique().tolist())
            
            if st.button("🚀 GENERAR DEUDA MASIVA (SEGÚN FILTRO)"):
                df_procesar = df_cont if filtro_inm == "TODOS" else df_cont[df_cont['Inmueble'] == filtro_inm]
                for _, row in df_procesar.iterrows():
                    db_query("INSERT INTO deudas (id_contrato, concepto, monto_debe) VALUES (?, ?, ?)", (row['id'], mes_txt, row['monto_alquiler']), commit=True)
                st.success(f"Se generaron {len(df_procesar)} deudas de alquiler exitosamente.")
            
            st.write("---")
            st.subheader("Acciones de Contrato")
            c_id_sel = st.selectbox("Seleccione ID de Contrato para eliminar", df_cont['id'].tolist())
            if st.button("🚨 ANULAR CONTRATO SELECCIONADO"):
                db_query(f"DELETE FROM contratos WHERE id={c_id_sel}", commit=True); st.rerun()
