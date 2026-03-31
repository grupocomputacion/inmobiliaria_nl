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
# 2. NUEVO CONTRATO + PDF (V.5.3 - AUTO-REFRESH)
# ==========================================
elif menu == "📝 Nuevo Contrato":
    st.header("Formalización de Contrato y PDF")
    
    u_df = db_query("""
        SELECT i.id, b.nombre || ' - ' || i.tipo as ref, b.direccion, b.barrio, b.localidad, 
               i.tipo, i.precio_alquiler, i.costo_contrato, i.deposito_base 
        FROM inmuebles i JOIN bloques b ON i.id_bloque=b.id
    """)
    i_df = db_query("SELECT * FROM inquilinos")
    
    if u_df is not None and i_df is not None and not u_df.empty:
        # --- PASO 1: SELECCIÓN FUERA DEL FORM ---
        # Esto permite que al cambiar la unidad, Streamlit recargue la página y actualice sel_u
        st.subheader("1. Selección de Unidad")
        uid = st.selectbox("Elija la Unidad para el contrato", u_df['id'], 
                           format_func=lambda x: u_df[u_df['id']==x]['ref'].values[0])
        
        # Obtenemos los datos actualizados de la unidad seleccionada
        sel_u = u_df[u_df['id'] == uid].iloc[0]
        
        st.write("---")
        st.subheader("2. Datos del Contrato")
        
        # --- PASO 2: FORMULARIO PARA DATOS VARIABLES ---
        with st.form("f_contrato_v53"):
            col1, col2 = st.columns(2)
            
            # El Inquilino puede ir dentro porque no dispara cambios en otros campos
            iid = col1.selectbox("Inquilino", i_df['id'], 
                                 format_func=lambda x: i_df[i_df['id']==x]['nombre'].values[0])
            
            fini = col2.date_input("Fecha Inicio", date.today())
            meses = col1.number_input("Cantidad de Meses", min_value=1, max_value=60, value=3)
            
            st.write("**Montos sugeridos (puede editarlos):**")
            c_m1, c_m2, c_m3 = st.columns(3)
            
            # Ahora estos inputs toman el valor de sel_u actualizado
            ma = c_m1.text_input("Alquiler Mensual", f_m(sel_u['precio_alquiler']))
            md = c_m2.text_input("Depósito Garantía", f_m(sel_u['deposito_base']))
            mc = c_m3.text_input("Gasto Administrativo", f_m(sel_u['costo_contrato']))
            
            if st.form_submit_button("GRABAR Y GENERAR PDF"):
                f_vence = fini + timedelta(days=meses * 30)
                
                # Grabar Contrato
                cid = db_query("""INSERT INTO contratos (id_inmueble, id_inquilino, fecha_inicio, fecha_fin, monto_alquiler) 
                                 VALUES (?,?,?,?,?)""", (uid, iid, fini, f_vence, cl(ma)), commit=True)
                
                # Generar deudas iniciales
                db_query("INSERT INTO deudas (id_contrato, concepto, monto_debe) VALUES (?, 'Mes 1 Alquiler', ?)", (cid, cl(ma)), commit=True)
                db_query("INSERT INTO deudas (id_contrato, concepto, monto_debe) VALUES (?, 'Garantía/Depósito', ?)", (cid, cl(md)), commit=True)
                db_query("INSERT INTO deudas (id_contrato, concepto, monto_debe) VALUES (?, 'Gastos Administrativos', ?)", (cid, cl(mc)), commit=True)
                
                try:
                    pdf_bytes = generar_pdf_v5(sel_u, i_df[i_df['id']==iid].iloc[0], fini, ma, md, mc)
                    st.session_state['pdf_ready'] = bytes(pdf_bytes) 
                    st.session_state['cid_last'] = cid
                    st.success(f"Contrato {cid} grabado. Vence el {f_vence.strftime('%d/%m/%Y')}")
                    st.rerun() # Forzamos recarga para mostrar el botón de descarga
                except Exception as e:
                    st.error(f"Error al generar PDF: {e}")

        # Botón de descarga (fuera del form)
        if 'pdf_ready' in st.session_state:
            st.write("---")
            st.download_button("📥 DESCARGAR CONTRATO PDF", 
                               st.session_state['pdf_ready'], 
                               f"Contrato_NL_{st.session_state.get('cid_last', 'nuevo')}.pdf", 
                               "application/pdf")
    else:
        st.warning("Debe cargar Inmuebles, Unidades e Inquilinos en 'Maestros' primero.")


# ==========================================
# 3. COBRANZAS (V.8.1 - TOTAL RESET)
# ==========================================
elif menu == "💰 Cobranzas":
    st.header("Gestión de Cobranzas y Pagos")
    
    # 1. Consulta de deudas (trae lo que realmente hay en la base)
    deu_pend = db_query("""
        SELECT 
            d.id as id_deuda, 
            inq.nombre as Inquilino, 
            b.nombre || ' - ' || i.tipo as Referencia,
            d.concepto as Concepto, 
            d.monto_debe - IFNULL(d.monto_pago, 0) as [Saldo Pendiente]
        FROM deudas d
        JOIN contratos c ON d.id_contrato = c.id
        JOIN inmuebles i ON c.id_inmueble = i.id
        JOIN bloques b ON i.id_bloque = b.id
        JOIN inquilinos inq ON c.id_inquilino = inq.id
        WHERE d.pagado = 0
        ORDER BY inq.nombre, d.concepto
    """)

    # --- FUNCIÓN DE RESET TOTAL ---
    def limpiar_pantalla():
        # Borramos el PDF de la memoria
        if 'pdf_data' in st.session_state:
            del st.session_state['pdf_data']
        # Borramos los valores de los inputs (esto obliga a los campos a vaciarse)
        if 'monto_usuario_final' in st.session_state:
            del st.session_state['monto_usuario_final']
        if 'sel_deudas_key' in st.session_state:
            del st.session_state['sel_deudas_key']
        st.rerun()

    if deu_pend is not None and not deu_pend.empty:
        with st.form("f_cobranza_final", clear_on_submit=False):
            st.subheader("Detalle de la Operación")
            
            # Agregamos una KEY al multiselect para poder resetearlo
            indices_sel = st.multiselect(
                "Deudas a incluir en este pago:",
                deu_pend.index.tolist(),
                format_func=lambda x: f"{deu_pend.loc[x, 'Inquilino']} | {deu_pend.loc[x, 'Concepto']} | ${deu_pend.loc[x, 'Saldo Pendiente']}",
                key="sel_deudas_key"
            )
            
            total_marcado = 0.0
            if indices_sel:
                total_marcado = float(deu_pend.loc[indices_sel, 'Saldo Pendiente'].sum())
            
            st.markdown(f"### Total Deuda Seleccionada: :blue[${total_marcado:,.2f}]")
            st.write("---")
            
            col1, col2 = st.columns(2)
            fecha_pago = col1.date_input("Fecha de Cobro", date.today())
            
            # Este campo ahora es esclavo del total_marcado a menos que lo edites
            monto_a_grabar = col2.number_input(
                "Monto REAL recibido ($):", 
                min_value=0.0, 
                value=total_marcado,
                key="monto_usuario_final"
            )
            
            btn_procesar = st.form_submit_button("✅ REGISTRAR PAGO Y GENERAR PDF")

        if btn_procesar:
            # Usamos el valor real que escribió el usuario
            monto_final = st.session_state.monto_usuario_final
            
            if not indices_sel:
                st.error("Seleccione al menos una deuda.")
            elif monto_final <= 0:
                st.error("El monto debe ser mayor a 0.")
            else:
                try:
                    saldo_disponible = monto_final
                    filas_sel = deu_pend.loc[indices_sel]
                    inquilino_n = filas_sel.iloc[0]['Inquilino']
                    detalles_pago = []

                    for _, fila in filas_sel.iterrows():
                        if saldo_disponible <= 0: break
                        id_d = fila['id_deuda']
                        pendiente = float(fila['Saldo Pendiente'])
                        
                        if saldo_disponible >= pendiente:
                            cobro_actual = pendiente
                            esta_pagado = 1
                            saldo_disponible -= pendiente
                            txt_estado = "(Cancelado)"
                        else:
                            cobro_actual = saldo_disponible
                            esta_pagado = 0
                            saldo_disponible = 0
                            txt_estado = "(Pago Parcial)"

                        db_query("""
                            UPDATE deudas SET monto_pago = IFNULL(monto_pago, 0) + ?, 
                            pagado = ?, fecha_pago = ? WHERE id = ?
                        """, (cobro_actual, esta_pagado, fecha_pago, id_d), commit=True)
                        
                        detalles_pago.append(f"{fila['Concepto']} - {fila['Referencia']} {txt_estado}: ${cobro_actual}")

                    # --- PDF CON FIRMA Y CUIT ---
                    pdf = PDFRecibo()
                    pdf.add_page()
                    pdf.set_font('Arial', 'B', 14)
                    pdf.cell(0, 10, "COMPROBANTE DE PAGO", ln=True, align='C')
                    pdf.ln(5)
                    pdf.set_font('Arial', '', 11)
                    pdf.cell(0, 8, f"Inquilino: {inquilino_n}", ln=True)
                    pdf.cell(0, 8, f"Fecha: {fecha_pago.strftime('%d/%m/%Y')}", ln=True)
                    pdf.cell(0, 8, f"DNI/CUIT: 30-71884850-0", ln=True)
                    pdf.set_font('Arial', 'B', 11)
                    pdf.cell(0, 10, f"TOTAL RECIBIDO: $ {monto_final:,.2f}", ln=True)
                    pdf.ln(5)
                    for item in detalles_pago:
                        pdf.cell(0, 6, f"  > {item}", ln=True)

                    pdf.ln(25)
                    pdf.cell(60, 0, '', 'T', 0, 'C') 
                    pdf.ln(2)
                    pdf.set_font('Arial', 'B', 10)
                    pdf.cell(60, 5, "NL INMOBILIARIA", 0, 1, 'C')

                    res_pdf = pdf.output(dest='S')
                    st.session_state['pdf_data'] = bytes(res_pdf, 'latin-1') if isinstance(res_pdf, str) else bytes(res_pdf)
                    
                    st.success(f"Cobro procesado por ${monto_final}. ¡Recibo generado!")
                    st.rerun()

                except Exception as e:
                    st.error(f"Error: {e}")

    # --- SECCIÓN DE DESCARGA Y RESET TOTAL ---
    if 'pdf_data' in st.session_state:
        st.divider()
        col_down, col_reset = st.columns(2)
        
        col_down.download_button(
            "📥 DESCARGAR RECIBO PDF", 
            st.session_state['pdf_data'], 
            f"Recibo_{date.today()}.pdf", 
            "application/pdf",
            use_container_width=True
        )
        
        # Este botón ahora llama a la función de limpieza profunda
        if col_reset.button("🔄 NUEVA COBRANZA (Limpiar todo)", use_container_width=True):
            limpiar_pantalla()

    elif deu_pend is None or deu_pend.empty:
        st.success("✅ No hay deudas pendientes.")
        
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
# 6. MAESTROS (V.8.5 - VERSIÓN FINAL CONSOLIDADA)
# ==========================================
elif menu == "⚙️ Maestros":
    st.header("Panel de Administración y Maestros")
    
    # Definición de las 7 pestañas solicitadas
    t1, t2, t3, t4, t5, t6, t7 = st.tabs([
        "🏢 Inmuebles", "🏠 Unidades", "👤 Inquilinos", 
        "📋 Contratos", "💾 Backup", "📋 Alquilados", "⚙️ Generación Mensual"
    ])

    # --- 1. INMUEBLES (EDIFICIOS) ---
    with t1:
        st.subheader("Gestión de Edificios / Complejos")
        with st.expander("➕ Cargar Nuevo Inmueble"):
            with st.form("f_inm_alta", clear_on_submit=True):
                c1, c2 = st.columns(2)
                n = c1.text_input("Nombre del Edificio")
                d = c1.text_input("Dirección")
                b = c2.text_input("Barrio")
                l = c2.text_input("Localidad")
                if st.form_submit_button("Guardar Inmueble"):
                    db_query("INSERT INTO bloques (nombre, direccion, barrio, localidad) VALUES (?,?,?,?)", (n, d, b, l), commit=True)
                    st.success("Inmueble guardado.")
                    st.rerun()
        
        df_inm = db_query("SELECT id, nombre as Nombre, direccion as Dirección, barrio as Barrio, localidad as Localidad FROM bloques")
        if df_inm is not None and not df_inm.empty:
            st.write("**Lista de Inmuebles:**")
            # Mostramos la tabla ocultando el ID técnico
            st.dataframe(df_inm.drop(columns=['id']), use_container_width=True, hide_index=True)

    # --- 2. UNIDADES (DEPARTAMENTOS) ---
    with t2:
        st.subheader("Gestión de Unidades Individuales")
        df_b_ref = db_query("SELECT id, nombre FROM bloques")
        if df_b_ref is not None and not df_b_ref.empty:
            with st.expander("➕ Cargar Nueva Unidad"):
                with st.form("f_u_alta", clear_on_submit=True):
                    bid = st.selectbox("Inmueble Perteneciente", df_b_ref['id'], format_func=lambda x: df_b_ref[df_b_ref['id']==x]['nombre'].values[0])
                    tipo = st.text_input("Descripción (Ej: Depto 1A / Local 2)")
                    c1, c2, c3 = st.columns(3)
                    p1 = c1.text_input("Alquiler")
                    p2 = c2.text_input("Contrato")
                    p3 = c3.text_input("Deposito")
                    if st.form_submit_button("Crear Unidad"):
                        db_query("INSERT INTO inmuebles (id_bloque, tipo, precio_alquiler, costo_contrato, deposito_base) VALUES (?,?,?,?,?)", (bid, tipo, cl(p1), cl(p2), cl(p3)), commit=True)
                        st.success("Unidad creada con éxito.")
                        st.rerun()
            
            # Vista de Unidades con nombres de columnas corregidos
            df_uni = db_query("""SELECT i.id, b.nombre as Inmueble, i.tipo as Unidad, 
                                 i.precio_alquiler as Alquiler, i.costo_contrato as Contrato, 
                                 i.deposito_base as Deposito 
                                 FROM inmuebles i JOIN bloques b ON i.id_bloque = b.id""")
            if df_uni is not None and not df_uni.empty:
                df_u_show = df_uni.drop(columns=['id']).copy()
                for col in ['Alquiler', 'Contrato', 'Deposito']: 
                    df_u_show[col] = df_u_show[col].apply(f_m)
                st.dataframe(df_u_show, use_container_width=True, hide_index=True)

    # --- 3. INQUILINOS (CON CORRECCIÓN DOMICILIO) ---
    with t3:
        st.subheader("Registro de Inquilinos")
        with st.expander("➕ Cargar Nuevo Inquilino"):
            with st.form("f_inq_alta", clear_on_submit=True):
                c1, c2 = st.columns(2)
                n = c1.text_input("Nombre y Apellido")
                dni = c1.text_input("DNI / CUIT")
                cel = c1.text_input("WhatsApp")
                dom = c2.text_input("Domicilio") # Sustituye Procedencia
                gru = c2.text_input("Grupo / Referencia")
                eme = c2.text_input("Emergencia")
                if st.form_submit_button("Guardar Inquilino"):
                    db_query("INSERT INTO inquilinos (nombre, dni, celular, procedencia, grupo, emergencia) VALUES (?,?,?,?,?,?)", (n, dni, cel, dom, gru, eme), commit=True)
                    st.rerun()
        
        df_inq = db_query("SELECT id, nombre as Nombre, dni as DNI, celular as WhatsApp, procedencia as Domicilio, grupo as Grupo, emergencia as Emergencia FROM inquilinos")
        if df_inq is not None and not df_inq.empty:
            st.dataframe(df_inq.drop(columns=['id']), use_container_width=True, hide_index=True)
            st.write("---")
            sel_inq = st.selectbox("Seleccione Inquilino para EDITAR", df_inq['Nombre'].tolist())
            i_dat = df_inq[df_inq['Nombre'] == sel_inq].iloc[0]
            
            with st.form("f_inq_edit"):
                c1, c2 = st.columns(2)
                en_n = c1.text_input("Nombre", i_dat['Nombre'])
                en_d = c1.text_input("DNI", i_dat['DNI'])
                en_c = c1.text_input("WhatsApp", i_dat['WhatsApp'])
                en_p = c2.text_input("Domicilio", i_dat['Domicilio'])
                en_g = c2.text_input("Grupo", i_dat['Grupo'])
                en_e = c2.text_input("Emergencia", i_dat['Emergencia'])
                if st.form_submit_button("💾 Actualizar Datos"):
                    db_query("UPDATE inquilinos SET nombre=?, dni=?, celular=?, procedencia=?, grupo=?, emergencia=? WHERE id=?", (en_n, en_d, en_c, en_p, en_g, en_e, int(i_dat['id'])), commit=True)
                    st.success("Datos actualizados.")
                    st.rerun()

    # --- 4. CONTRATOS (GESTIÓN DE BAJAS) ---
    with t4:
        st.subheader("Contratos Vigentes")
        df_cont = db_query("""SELECT c.id as ID_Contrato, b.nombre as Inmueble, i.tipo as Unidad, inq.nombre as Inquilino, c.fecha_inicio as Inicio, c.monto_alquiler as [Alquiler]
                             FROM contratos c JOIN inmuebles i ON c.id_inmueble = i.id 
                             JOIN bloques b ON i.id_bloque = b.id JOIN inquilinos inq ON c.id_inquilino = inq.id WHERE c.activo = 1""")
        if df_cont is not None and not df_cont.empty:
            st.dataframe(df_cont, use_container_width=True, hide_index=True)
            sel_c = st.selectbox("Seleccione ID de Contrato para FINALIZAR", df_cont['ID_Contrato'].tolist())
            if st.button("🚨 DAR DE BAJA CONTRATO"):
                db_query(f"UPDATE contratos SET activo=0 WHERE id={sel_c}", commit=True)
                st.warning(f"Contrato {sel_c} dado de baja.")
                st.rerun()

    # --- 5. BACKUP INTEGRAL (INCLUYE DEUDAS) ---
    with t5:
        st.subheader("💾 Backup y Recuperación")
        c_exp, c_imp = st.columns(2)
        with c_exp:
            if st.button("Generar Respaldo Completo"):
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    for tabla, hoja in [('bloques','Inmuebles'), ('inmuebles','Unidades'), ('inquilinos','Inquilinos'), ('contratos','Contratos'), ('deudas','Deudas')]:
                        df_tmp = db_query(f"SELECT * FROM {tabla}")
                        if df_tmp is not None: df_tmp.to_excel(writer, sheet_name=hoja, index=False)
                st.download_button("📥 Descargar Excel", output.getvalue(), f"Backup_NL_{date.today()}.xlsx")

        with c_imp:
            archivo = st.file_uploader("Subir Backup para Restaurar", type=["xlsx"])
            if archivo and st.button("🚀 Restaurar Todo"):
                dfs = pd.read_excel(archivo, sheet_name=None)
                mapping = {'Inmuebles':'bloques', 'Unidades':'inmuebles', 'Inquilinos':'inquilinos', 'Contratos':'contratos', 'Deudas':'deudas'}
                with sqlite3.connect('datos_alquileres.db') as conn:
                    for hoja, tabla in mapping.items():
                        if hoja in dfs:
                            conn.execute(f"DELETE FROM {tabla}")
                            dfs[hoja].to_sql(tabla, conn, if_exists='append', index=False)
                st.success("Restauración completa.")
                st.rerun()

    # --- 6. LISTADO DE ALQUILADOS (TABLERO DE CONTROL) ---
    with t6:
        st.subheader("📋 Unidades Ocupadas y Saldo")
        df_alq = db_query("""
            SELECT b.nombre as Inmueble, i.tipo as Unidad, inq.nombre as Inquilino, inq.procedencia as Domicilio, inq.celular as [WhatsApp],
                   IFNULL((SELECT SUM(monto_debe - monto_pago) FROM deudas WHERE id_contrato = c.id AND pagado = 0), 0) as Saldo_Pendiente
            FROM contratos c JOIN inmuebles i ON c.id_inmueble = i.id JOIN bloques b ON i.id_bloque = b.id JOIN inquilinos inq ON c.id_inquilino = inq.id
            WHERE c.activo = 1 ORDER BY b.nombre
        """)
        if df_alq is not None and not df_alq.empty:
            df_view = df_alq.copy()
            df_view['Saldo_Pendiente'] = df_view['Saldo_Pendiente'].apply(lambda x: f"🔴 $ {f_m(x)}" if x > 0 else "🟢 Al día")
            st.dataframe(df_view, use_container_width=True, hide_index=True)
            st.metric("Total Cobranza Pendiente", f"$ {f_m(df_alq['Saldo_Pendiente'].sum())}")

    # --- 7. GENERACIÓN MENSUAL (AUTOMATIZACIÓN) ---
    with t7:
        st.subheader("⚙️ Generación de Deuda de Alquiler")
        with st.form("f_gen"):
            mes = st.selectbox("Mes", ["Enero","Febrero","Marzo","Abril","Mayo","Junio","Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"])
            anio = st.number_input("Año", value=2026)
            if st.form_submit_button("Generar Alquileres de este Mes"):
                contratos = db_query("SELECT id, monto_alquiler FROM contratos WHERE activo=1")
                for _, c in contratos.iterrows():
                    concepto = f"Alquiler {mes} {anio}"
                    check = db_query("SELECT id FROM deudas WHERE id_contrato=? AND concepto=?", (int(c['id']), concepto))
                    if check is None or check.empty:
                        db_query("INSERT INTO deudas (id_contrato, concepto, monto_debe, monto_pago, pagado) VALUES (?,?, ?, 0, 0)", (int(c['id']), concepto, int(c['monto_alquiler'])), commit=True)
                st.success("Proceso masivo terminado.")


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
