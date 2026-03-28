import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, date, timedelta
import os
import io
from fpdf import FPDF

# 1. DEFINICIÓN DE LA CLASE PDF (FUERA DEL MENÚ)
class PDFRecibo(FPDF):
    def header(self):
        if os.path.exists("alquileres.jpg"):
            self.image("alquileres.jpg", 10, 8, 30)
        self.set_font('Arial', 'B', 16)
        self.cell(80)
        self.cell(30, 10, 'RECIBO OFICIAL DE PAGO', 0, 0, 'C')
        self.ln(20)

# --- FUNCIONES DE SOPORTE CRÍTICAS ---

def cl(t): 
    """ Limpia strings de moneda y los convierte a entero para la DB """
    try:
        if not t: return 0
        return int(str(t).replace('$', '').replace('.', '').replace(',', '').strip())
    except:
        return 0

def f_m(v): 
    """ Formatea números enteros a string con separador de miles '.' """
    try:
        return f"{int(v or 0):,}".replace(",", ".")
    except:
        return "0"

def db_query(sql, params=(), commit=False):
    """ Ejecuta consultas en SQLite de forma segura """
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
# 2. MOTOR DE DATOS CON MIGRACIÓN SEGURA (V.6.0)
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
        # Si falla una consulta por columna inexistente, no explota la app
        return None

def mantenimiento_base():
    """ Revisa y actualiza la estructura sin borrar datos """
    with sqlite3.connect('datos_alquileres.db') as conn:
        cur = conn.cursor()
        
        # 1. Crear tablas si no existen
        cur.execute("CREATE TABLE IF NOT EXISTS bloques (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT)")
        cur.execute("CREATE TABLE IF NOT EXISTS inquilinos (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT)")
        cur.execute("CREATE TABLE IF NOT EXISTS inmuebles (id INTEGER PRIMARY KEY AUTOINCREMENT, id_bloque INTEGER, tipo TEXT)")
        cur.execute("CREATE TABLE IF NOT EXISTS contratos (id INTEGER PRIMARY KEY AUTOINCREMENT, id_inmueble INTEGER, id_inquilino INTEGER)")
        cur.execute("CREATE TABLE IF NOT EXISTS deudas (id INTEGER PRIMARY KEY AUTOINCREMENT, id_contrato INTEGER, concepto TEXT)")

        # 2. DICCIONARIO DE COLUMNAS NECESARIAS (El 'Seguro de Vida' de los datos)
        # Formato: (Tabla, Columna, Tipo)
        columnas_plan = [
            ("bloques", "direccion", "TEXT"),
            ("bloques", "barrio", "TEXT"),
            ("bloques", "localidad", "TEXT"),
            ("inmuebles", "precio_alquiler", "INTEGER"),
            ("inmuebles", "costo_contrato", "INTEGER"),
            ("inmuebles", "deposito_base", "INTEGER"),
            ("inquilinos", "dni", "TEXT"),
            ("inquilinos", "celular", "TEXT"),
            ("inquilinos", "procedencia", "TEXT"),
            ("inquilinos", "grupo", "TEXT"),
            ("inquilinos", "emergencia", "TEXT"),
            ("contratos", "fecha_inicio", "DATE"),
            ("contratos", "fecha_fin", "DATE"),
            ("contratos", "monto_alquiler", "INTEGER"),
            ("contratos", "activo", "INTEGER DEFAULT 1"),
            ("deudas", "monto_debe", "INTEGER"),
            ("deudas", "monto_pago", "INTEGER DEFAULT 0"),
            ("deudas", "pagado", "INTEGER DEFAULT 0"),
            ("deudas", "fecha_pago", "DATE")
        ]

        # Inyectar columnas faltantes una por una
        for tabla, columna, tipo in columnas_plan:
            try:
                cur.execute(f"ALTER TABLE {tabla} ADD COLUMN {columna} {tipo}")
            except sqlite3.OperationalError:
                # Si la columna ya existe, SQLite da error y simplemente la salteamos
                pass
        conn.commit()

# Ejecutar SIEMPRE al iniciar
mantenimiento_base()

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
    
# ELIMINAMOS el .encode('latin-1') del final porque output(dest='S') ya entrega bytes
    return pdf.output(dest='S')


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

# ==========================================
# 1. INVENTARIO (V.6.9 - ESTRUCTURA CORREGIDA)
# ==========================================
if menu == "🏠 Inventario":
    st.header("Estado de Unidades y Disponibilidad")
    
    try:
        # Consulta completa con Disponibilidad
        query_inv = """
            SELECT 
                b.nombre as Inmueble, 
                i.tipo as Unidad, 
                i.precio_alquiler as Alquiler, 
                i.costo_contrato as Contrato, 
                i.deposito_base as Deposito,
                CASE WHEN c.activo = 1 THEN '🔴 OCUPADO' ELSE '🟢 LIBRE' END as Estado,
                CASE 
                    WHEN c.activo = 1 THEN c.fecha_fin 
                    ELSE 'DISPONIBLE HOY' 
                END as [Disponible Desde]
            FROM inmuebles i 
            JOIN bloques b ON i.id_bloque = b.id
            LEFT JOIN contratos c ON i.id = c.id_inmueble AND c.activo = 1
        """
        df = db_query(query_inv)
    except Exception as e:
        # Si falla (por falta de columnas), hacemos una consulta básica de emergencia
        query_basica = """
            SELECT b.nombre as Inmueble, i.tipo as Unidad, i.precio_alquiler as Alquiler
            FROM inmuebles i JOIN bloques b ON i.id_bloque = b.id
        """
        df = db_query(query_basica)
        st.warning("Nota: Algunas columnas de disponibilidad no están listas. Resetee la base si es necesario.")

    # AHORA SÍ: Validamos si hay datos después del bloque try/except
    if df is not None and not df.empty:
        c1, c2 = st.columns(2)
        total_u = len(df)
        
        # Conteo de libres (manejo de error si la columna no existe)
        if 'Estado' in df.columns:
            libres_count = len(df[df['Estado'].str.contains('LIBRE', na=False)])
        else:
            libres_count = 0
            
        c1.metric("Unidades Libres", libres_count)
        c2.metric("Total Unidades", total_u)
        
        # Formateo de moneda a las columnas que existan
        for col in ['Alquiler', 'Contrato', 'Deposito']:
            if col in df.columns:
                df[col] = df[col].apply(f_m)
        
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("No hay unidades cargadas en el sistema. Vaya a 'Maestros' para iniciar.")

        
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
                    
                    # Verificación de seguridad: si es bytearray, Streamlit lo acepta, 
                    # pero lo ideal es pasarle bytes puros.
                    st.session_state['pdf_ready'] = bytes(pdf_bytes) 
                    st.session_state['cid_last'] = cid
                    st.success(f"Contrato {cid} grabado. Vence el {f_vence.strftime('%d/%m/%Y')}")
                except Exception as e:
                    st.error(f"Error al generar PDF: {e}")
        if 'pdf_ready' in st.session_state:
            st.write("---")
            st.download_button("📥 DESCARGAR CONTRATO PDF", st.session_state['pdf_ready'], f"Contrato_NL_{st.session_state['cid_last']}.pdf", "application/pdf")
    else:
        st.warning("Debe cargar Inmuebles, Unidades e Inquilinos en 'Maestros' primero.")


# ==========================================
# 3. COBRANZAS (V.7.5 - FINAL CORREGIDA)
# ==========================================
elif menu == "💰 Cobranzas":
    if deu_pend is not None and not deu_pend.empty:    
       deu_pend_display = deu_pend.copy()
    
       with st.form("f_cobranza_masiva"):
           st.write("**Configuración del Cobro**")
        
           sel_rows = st.multiselect(
            "Marque las deudas a abonar:",
            deu_pend_display.index.tolist(),
            format_func=lambda x: f"{deu_pend_display.loc[x, 'Inquilino']} - {deu_pend_display.loc[x, 'Concepto']} (${deu_pend_display.loc[x, 'Saldo Pendiente']})"
           )
        
        # Estas variables deben inicializarse para que el form las reconozca
        monto_real = 0.0
        
        if sel_rows:
            deudas_sel = deu_pend.loc[sel_rows]
            total_teorico = deudas_sel['Saldo Pendiente'].sum()
            
            c1, c2 = st.columns(2)
            c1.metric("Suma Deudas Seleccionadas", f"$ {total_teorico}")
            
            # KEY IMPORTANTE: Evita que Streamlit pise tu valor al recargar
            monto_input = c2.text_input("Monto Total Recibido:", value=str(total_teorico), key="monto_manual")
            fecha_cobro = c1.date_input("Fecha de Cobro", date.today())
            
            # Limpiamos y convertimos a número
            try:
                monto_real = float(cl(monto_input)) if monto_input else 0.0
            except:
                monto_real = 0.0
        
        procesar_pago = st.form_submit_button("✅ PROCESAR PAGO Y GENERAR RECIBO")

    if procesar_pago:
        if not sel_rows:
            st.error("Seleccione deudas.")
        elif monto_real <= 0:
            st.error("El monto debe ser mayor a 0.")
        else:
            try:
                # --- LÓGICA DE IMPUTACIÓN ---
                saldo_restante = monto_real
                deudas_sel = deu_pend.loc[sel_rows]
                inq_data = deudas_sel.iloc[0]
                detalles_recibo = []

                for _, deuda in deudas_sel.iterrows():
                    if saldo_restante <= 0: break
                    
                    id_deuda_sql = deuda['id_deuda']
                    saldo_deuda = float(deuda['Saldo Pendiente'])
                    
                    if saldo_restante >= saldo_deuda:
                        # Pago total de esta deuda
                        imputar = saldo_deuda
                        pagado_flag = 1
                        saldo_restante -= saldo_deuda
                        tipo_txt = "(Pago Completo)"
                    else:
                        # Pago PARCIAL: El monto recibido no alcanza para esta deuda
                        imputar = saldo_restante
                        pagado_flag = 0 # SE MANTIENE COMO NO PAGADA
                        saldo_restante = 0
                        tipo_txt = "(Pago Parcial)"

                    # ACTUALIZACIÓN EN DB (Aseguramos el commit)
                    db_query("""
                        UPDATE deudas 
                        SET monto_pago = IFNULL(monto_pago, 0) + ?, 
                            pagado = ?, 
                            fecha_pago = ? 
                        WHERE id = ?""", (imputar, pagado_flag, fecha_cobro, id_deuda_sql), commit=True)
                    
                    detalles_recibo.append(f"{deuda['Concepto']} {tipo_txt}: ${imputar}")

                # --- GENERAR PDF ---
                pdf = PDFRecibo()
                pdf.add_page()
                pdf.set_font('Arial', 'B', 12)
                pdf.cell(0, 10, f"RECIBO PARA: {inq_data['Inquilino']}", ln=1)
                pdf.set_font('Arial', '', 11)
                pdf.cell(0, 10, f"Total Cobrado: $ {monto_real}", ln=1)
                for det in detalles_recibo:
                    pdf.cell(0, 7, f"- {det}", ln=1)
                
                # REFUERZO DE SEGURIDAD PARA EL ERROR DE BYTES:
                st.session_state['recibo_pdf'] = bytes(pdf.output(dest='S'), 'latin-1') if isinstance(pdf.output(dest='S'), str) else bytes(pdf.output(dest='S'))
                st.session_state['inquilino_ws'] = inq_data['WhatsApp']
                st.session_state['total_cobrado'] = monto_real
                
                st.success(f"Registrado correctamente. Saldo restante del pago: {saldo_restante}")
                st.rerun()

            except Exception as e:
                st.error(f"Fallo en procesamiento: {e}")


                
# ==========================================

elif menu == "🚨 Morosos":
    st.header("Morosos")
    mora = db_query("SELECT inq.nombre, d.monto_debe FROM deudas d JOIN contratos c ON d.id_contrato=c.id JOIN inquilinos inq ON c.id_inquilino=inq.id WHERE d.pagado=0")
    if mora is not None: st.table(mora)

elif menu == "📊 Caja":
    st.header("Caja Mensual")
    df_c = db_query("SELECT fecha_pago, concepto, monto_pago FROM deudas WHERE pagado=1")
    if df_c is not None: st.dataframe(df_c)

# ==========================================
# 6. MAESTROS (V.6.8 - INTEGRACIÓN TOTAL)
# ==========================================
elif menu == "⚙️ Maestros":
    st.header("Administración de Base de Datos")
    
    # Definimos las 5 pestañas: las 4 de gestión + la de respaldo

    t1, t2, t3, t4, t5, t6, t7 = st.tabs([
        "🏢 Inmuebles",
        "🏠 Unidades",
        "👤 Inquilinos", 
        "📋 Contratos",
        "💾 Backup",
        "📋 Listado de Alquilados",
        "⚙️ Generación Mensual"
    ])
    # --- 1. INMUEBLES ---
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

    # --- 4. CONTRATOS ---
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

    # --- 5. BACKUP & RESTORE (MOVIDO AQUÍ) ---
    with t5:
        st.subheader("💾 Gestión de Respaldo y Recuperación")
        c_exp, c_imp = st.columns(2)
        
        with c_exp:
            st.write("**Exportar base de datos**")
            if st.button("Generar Archivo de Respaldo"):
                try:
                    output = io.BytesIO()
                    df_b = db_query("SELECT * FROM bloques")
                    df_i = db_query("SELECT * FROM inmuebles")
                    df_inq = db_query("SELECT * FROM inquilinos")
                    df_con = db_query("SELECT * FROM contratos")
                    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                        if df_b is not None: df_b.to_excel(writer, sheet_name='Inmuebles', index=False)
                        if df_i is not None: df_i.to_excel(writer, sheet_name='Unidades', index=False)
                        if df_inq is not None: df_inq.to_excel(writer, sheet_name='Inquilinos', index=False)
                        if df_con is not None: df_con.to_excel(writer, sheet_name='Contratos', index=False)
                    st.download_button("📥 Descargar Excel", output.getvalue(), f"Backup_NL_{date.today()}.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
                except Exception as e: st.error(f"Error: {e}")

        with c_imp:
            st.write("**Importar desde Excel**")
            archivo = st.file_uploader("Subir respaldo (.xlsx)", type=["xlsx"])
            if archivo and st.button("🚀 Iniciar Recuperación"):
                try:
                    dfs = pd.read_excel(archivo, sheet_name=None)
                    mapping = {'Inmuebles': 'bloques', 'Unidades': 'inmuebles', 'Inquilinos': 'inquilinos', 'Contratos': 'contratos'}
                    with sqlite3.connect('datos_alquileres.db') as conn:
                        for sheet, tabla in mapping.items():
                            if sheet in dfs:
                                conn.execute(f"DELETE FROM {tabla}") # Limpiamos antes de restaurar
                                dfs[sheet].to_sql(tabla, conn, if_exists='append', index=False)
                    st.success("✅ Datos restaurados."); st.rerun()
                except Exception as e: st.error(f"Error: {e}")

    # --- 6. LISTADO DE ALQUILADOS (NUEVA CONSULTA) ---
    with t6:
        st.subheader("Unidades Alquiladas y Contacto")
        
        query_alquilados = """
            SELECT 
                b.nombre as Inmueble, 
                i.tipo as Unidad, 
                inq.nombre as Inquilino, 
                inq.celular as [WhatsApp/Cel],
                IFNULL((SELECT SUM(monto_debe - monto_pago) FROM deudas WHERE id_contrato = c.id AND pagado = 0), 0) as Saldo_Pendiente
            FROM contratos c
            JOIN inmuebles i ON c.id_inmueble = i.id
            JOIN bloques b ON i.id_bloque = b.id
            JOIN inquilinos inq ON c.id_inquilino = inq.id
            WHERE c.activo = 1
        """
        
        df_alq = db_query(query_alquilados)
        
        if df_alq is not None and not df_alq.empty:
            # Aplicamos formato visual al saldo para que sea fácil de leer
            df_display = df_alq.copy()
            df_display['Saldo_Pendiente'] = df_display['Saldo_Pendiente'].apply(lambda x: f"🔴 $ {f_m(x)}" if x > 0 else "🟢 Al día")
            
            st.dataframe(df_display, use_container_width=True, hide_index=True)
            
            # Botón para descargar este listado específico a Excel si lo necesita
            output_list = io.BytesIO()
            with pd.ExcelWriter(output_list, engine='xlsxwriter') as writer:
                df_alq.to_excel(writer, sheet_name='Alquilados', index=False)
            
            st.download_button(
                label="📥 Exportar Listado a Excel",
                data=output_list.getvalue(),
                file_name=f"Alquilados_Contacto_{date.today()}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            st.info("No hay unidades con contratos activos en este momento.")                

    # --- 7. GENERACIÓN MASIVA DE DEUDAS (NUEVA FUNCIÓN) ---
    with t7:
        st.subheader("Generación de Alquileres del Mes")
        st.info("Esta herramienta creará el cargo de alquiler para TODOS los contratos activos en el mes seleccionado.")
        
        with st.form("f_generacion_masiva"):
            c1, c2 = st.columns(2)
            mes_gen = c1.selectbox("Mes a generar", 
                                   ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", 
                                    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"],
                                   index=date.today().month - 1)
            anio_gen = c2.number_input("Año", value=date.today().year, step=1)
            
            confirmar = st.checkbox("Confirmo que deseo generar los cargos para todos los contratos activos.")
            
            if st.form_submit_button("🚀 Generar Cargos Masivos"):
                if confirmar:
                    # Traemos todos los contratos activos
                    contratos_activos = db_query("SELECT id, monto_alquiler FROM contratos WHERE activo = 1")
                    
                    if contratos_activos is not None and not contratos_activos.empty:
                        contador = 0
                        error_count = 0
                        concepto = f"Alquiler {mes_gen} {anio_gen}"
                        
                        for _, fila in contratos_activos.iterrows():
                            try:
                                # Verificamos si ya existe el cargo para evitar duplicados
                                check = db_query("SELECT id FROM deudas WHERE id_contrato=? AND concepto=?", 
                                                (int(fila['id']), concepto))
                                
                                if check is None or check.empty:
                                    db_query("""INSERT INTO deudas (id_contrato, concepto, monto_debe, monto_pago, pagado) 
                                             VALUES (?, ?, ?, 0, 0)""", 
                                             (int(fila['id']), concepto, int(fila['monto_alquiler'])), commit=True)
                                    contador += 1
                            except:
                                error_count += 1
                        
                        if contador > 0:
                            st.success(f"✅ Se generaron {contador} cargos de alquiler exitosamente.")
                        if error_count > 0:
                            st.error(f"❌ Hubo errores en {error_count} registros.")
                        if contador == 0 and error_count == 0:
                            st.warning("No se generaron cargos nuevos (posiblemente ya existían para este mes).")
                        
                        st.rerun()
                    else:
                        st.warning("No se encontraron contratos activos para generar cargos.")
                else:
                    st.error("Por favor, marque la casilla de confirmación.")

# ==========================================
# 1. INVENTARIO (V.6.8 - VISTA LIMPIA)
# ==========================================
elif menu == "🏠 Inventario":
    st.header("Estado de Unidades y Disponibilidad")
    
    query_inv = """
        SELECT 
            b.nombre as Inmueble, 
            i.tipo as Unidad, 
            i.precio_alquiler as Alquiler, 
            i.costo_contrato as Contrato, 
            i.deposito_base as Deposito,
            CASE WHEN c.activo = 1 THEN '🔴 OCUPADO' ELSE '🟢 LIBRE' END as Estado,
            CASE 
                WHEN c.activo = 1 THEN c.fecha_fin 
                ELSE 'DISPONIBLE HOY' 
            END as [Disponible Desde]
        FROM inmuebles i 
        JOIN bloques b ON i.id_bloque = b.id
        LEFT JOIN contratos c ON i.id = c.id_inmueble AND c.activo = 1
    """
    df = db_query(query_inv)

    if df is not None and not df.empty:
        c1, c2 = st.columns(2)
        total_u = len(df)
        libres_count = len(df[df['Estado'].str.contains('LIBRE', na=False)])
        
        c1.metric("Unidades Libres", libres_count)
        c2.metric("Total Unidades", total_u)
        
        # Formateo de moneda
        cols_money = ['Alquiler', 'Contrato', 'Deposito']
        for col in cols_money:
            if col in df.columns:
                df[col] = df[col].apply(f_m)
        
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("No hay unidades cargadas en el sistema.")
