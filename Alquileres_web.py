import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, date, timedelta
import os
import io
from fpdf import FPDF

# --- ESTILO CSS REFORZADO (V.10.0) ---
st.markdown("""
    <style>
        /* Fondo del Sidebar */
        [data-testid="stSidebar"] {
            background-color: #1E1E1E !important;
        }
        /* Texto de los botones del menú en blanco puro */
        [data-testid="stSidebar"] .stRadio div label p {
            color: white !important;
            font-size: 1.1rem !important;
            font-weight: 500 !important;
        }
        /* Color de los íconos del menú */
        [data-testid="stSidebar"] .stRadio div label span {
            color: white !important;
        }
        /* Hover: cuando pasas el mouse por encima */
        [data-testid="stSidebar"] .stRadio div label:hover {
            background-color: #333333 !important;
            border-radius: 5px;
        }
    </style>
""", unsafe_allow_html=True)


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

def cl(texto):
    """Limpia el formato para guardar en la DB como número puro"""
    try:
        if isinstance(texto, (int, float)):
            return int(texto)
        # Quitamos el punto de miles para que Python lo procese como nro
        return int(str(texto).replace(".", "").replace("$", "").replace("U$D", "").strip())
    except:
        return 0

def f_m(valor):
    """Formatea montos: Sin decimales y con punto en miles (Ej: 1.500.000)"""
    try:
        if valor is None or valor == "":
            return "0"
        # Quitamos decimales convirtiendo a int y formateamos con punto
        return f"{int(float(valor)):,}".replace(",", ".")
    except:
        return "0"

def db_query(query, params=(), commit=False):
    import sqlite3
    import pandas as pd
    conn = sqlite3.connect('datos_alquileres.db')
    cur = conn.cursor()
    try:
        if commit:
            cur.execute(query, params)
            conn.commit()
            last_id = cur.lastrowid
            conn.close()
            return last_id
        else:
            df = pd.read_sql_query(query, conn, params=params)
            conn.close()
            return df
    except Exception as e:
        st.error(f"Error en la base de datos: {e}")
        conn.close()
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

# ==========================================
# TABLAS PARA GESTIÓN DE LOTES (NUEVAS)
# ==========================================
db_query("""CREATE TABLE IF NOT EXISTS desarrollos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT,
    ubicacion TEXT,
    localidad TEXT
)""", commit=True)

db_query("""CREATE TABLE IF NOT EXISTS lotes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    id_desarrollo INTEGER,
    manzana TEXT,
    nro_lote TEXT,
    metros_cuadrados REAL,
    frente REAL,
    fondo REAL,
    servicios TEXT,
    observaciones TEXT,
    precio_contado REAL,
    precio_financiado REAL,
    estado TEXT DEFAULT 'Libre',
    FOREIGN KEY(id_desarrollo) REFERENCES desarrollos(id)
)""", commit=True)

db_query("""CREATE TABLE IF NOT EXISTS compradores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT,
    dni_cuit TEXT,
    celular TEXT,
    domicilio TEXT,
    email TEXT
)""", commit=True)

db_query("""CREATE TABLE IF NOT EXISTS ventas_lotes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    id_lote INTEGER,
    id_comprador INTEGER,
    fecha_venta DATE,
    monto_total_usd REAL,
    entrega_usd REAL,
    cantidad_cuotas INTEGER,
    monto_cuota_usd REAL,
    estado TEXT DEFAULT 'Activa',
    FOREIGN KEY(id_lote) REFERENCES lotes(id),
    FOREIGN KEY(id_comprador) REFERENCES compradores(id)
)""", commit=True)

db_query("""CREATE TABLE IF NOT EXISTS cuotas_lotes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    id_venta INTEGER,
    nro_cuota INTEGER,
    monto_usd REAL,
    fecha_vencimiento DATE,
    pagado INTEGER DEFAULT 0,
    monto_pagado_usd REAL DEFAULT 0,
    fecha_pago DATE,
    FOREIGN KEY(id_venta) REFERENCES ventas_lotes(id)
)""", commit=True)        

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

def generar_pdf_lote(datos_pago, datos_comprador, datos_lote):
    pdf = FPDF()
    pdf.add_page()
    
    # Encabezado
    if os.path.exists("alquileres.jpg"):
        pdf.image("alquileres.jpg", 10, 8, 33)
    
    pdf.set_font('Arial', 'B', 15)
    pdf.cell(80)
    pdf.cell(30, 10, 'RECIBO DE PAGO - LOTES', 0, 0, 'C')
    pdf.ln(20)
    
    # Datos de la Empresa y Fecha
    pdf.set_font('Arial', '', 10)
    pdf.cell(100, 7, "NL INMOBILIARIA - GESTIÓN DE LOTEO", 0, 0, 'L')
    pdf.cell(90, 7, f"Fecha: {date.today().strftime('%d/%m/%Y')}", 0, 1, 'R')
    pdf.ln(10)
    
    # Cuerpo del Recibo
    pdf.set_font('Arial', 'B', 11)
    pdf.cell(0, 8, f"RECIBIMOS DE: {datos_comprador['nombre'].upper()}", 1, 1, 'L')
    pdf.ln(5)
    
    pdf.set_font('Arial', '', 11)
    pdf.cell(0, 8, f"La suma de: U$D {f_m(datos_pago['monto'])} (Dólares Estadounidenses)", 0, 1, 'L')
    pdf.cell(0, 8, f"En concepto de: {datos_pago['concepto']}", 0, 1, 'L')
    pdf.cell(0, 8, f"Referencia: Manzana {datos_lote['manzana']} - Lote {datos_lote['nro_lote']}", 0, 1, 'L')
    pdf.ln(15)
    
    # Firma
    pdf.ln(20)
    pdf.cell(110)
    pdf.cell(80, 7, "_______________________________", 0, 1, 'C')
    pdf.cell(110)
    pdf.cell(80, 7, "Firma Autorizada", 0, 1, 'C')

    return pdf.output(dest='S').encode('latin-1')


# ==========================================
# 4. BARRA LATERAL
# ==========================================
with st.sidebar:
    if os.path.exists("alquileres.jpg"): st.image("alquileres.jpg", use_container_width=True)
    st.info("🚀 SISTEMA NL V.5.0")
    menu = st.radio("MENÚ:", ["🏠 Inventario", "📝 Nuevo Contrato", "💰 Cobranzas", "🚨 Morosos", "📊 Caja", "⚙️ Maestros", "🌳 Lotes"])

# ==========================================
# 5. SECCIONES
# ==========================================


# ==========================================
# 1. INVENTARIO (V.12.5 - RECONSTRUIDO COMPLETO)
# ==========================================
if menu == "🏠 Inventario":
    st.header("Inventario Global de Unidades")

    # --- FILTROS DE VISTA (Manteniendo funcionalidad) ---
    c1, c2 = st.columns(2)
    df_bloques_filt = db_query("SELECT nombre FROM bloques")
    lista_inmuebles = ["Todos"] + df_bloques_filt['nombre'].tolist() if df_bloques_filt is not None else ["Todos"]
    sel_inmueble = c1.selectbox("🏢 Filtrar por Edificio:", lista_inmuebles)
    sel_estado = c2.selectbox("🔑 Filtrar por Disponibilidad:", ["Todos", "Libre", "Ocupado"])

    # --- CONSULTA ROBUSTA (Recuperando Alquiler, Contrato, Deposito y Fechas) ---
    query_inv = """
        SELECT 
            b.nombre as Inmueble,
            i.tipo as Unidad,
            i.precio_alquiler as Alquiler,
            i.costo_contrato as Contrato,
            i.deposito_base as Deposito,
            CASE 
                WHEN c.id IS NOT NULL THEN 'Ocupado'
                ELSE 'Libre'
            END as Estado,
            CASE 
                WHEN c.id IS NOT NULL THEN c.fecha_fin
                ELSE 'Inmediata'
            END as [Disponible Desde]
        FROM inmuebles i
        JOIN bloques b ON i.id_bloque = b.id
        LEFT JOIN contratos c ON i.id = c.id_inmueble AND c.activo = 1
        WHERE 1=1
    """
    
    if sel_inmueble != "Todos":
        query_inv += f" AND b.nombre = '{sel_inmueble}'"
    
    df_inv = db_query(query_inv)

    if df_inv is not None and not df_inv.empty:
        # Aplicar filtro de estado en el DataFrame si no es "Todos"
        if sel_estado != "Todos":
            df_inv = df_inv[df_inv['Estado'] == sel_estado]

        # --- MÉTRICAS ---
        m1, m2, m3 = st.columns(3)
        m1.metric("Total Unidades", len(df_inv))
        m2.metric("Ocupadas", len(df_inv[df_inv['Estado'] == 'Ocupado']))
        m3.metric("Libres", len(df_inv[df_inv['Estado'] == 'Libre']))

        st.write("---")

        # --- FORMATEO Y VISUALIZACIÓN ---
        df_show = df_inv.copy()
        
        # Formateamos montos a moneda
        for col in ['Alquiler', 'Contrato', 'Deposito']:
            df_show[col] = df_show[col].apply(f_m)
        
        # Formateamos la fecha de disponibilidad para que sea legible
        def format_fecha_disp(val):
            if val == 'Inmediata':
                return "✅ Inmediata"
            try:
                # Convertimos string a fecha y luego a formato DD/MM/YYYY
                d = pd.to_datetime(val).date()
                if d <= date.today():
                    return "✅ Inmediata (Contrato Vencido)"
                return f"⏳ {d.strftime('%d/%m/%Y')}"
            except:
                return val

        df_show['Disponible Desde'] = df_show['Disponible Desde'].apply(format_fecha_disp)

        # Estilo de colores para el Estado
        def color_estado(val):
            color = '#ff4b4b' if val == 'Ocupado' else '#28a745' # Rojo / Verde
            return f'color: {color}; font-weight: bold'

        st.dataframe(
            df_show.style.applymap(color_estado, subset=['Estado']),
            use_container_width=True,
            hide_index=True
        )
        
    else:
        st.info("No se encontraron unidades con los filtros seleccionados.")

        
# ==========================================
# 2. NUEVO CONTRATO + PDF (V.14.0 - FINAL)
# ==========================================
elif menu == "📝 Nuevo Contrato":
    st.header("Formalización de Contrato y PDF")
    
    # 1. CARGA DE DATOS MAESTROS
    u_df = db_query("""
        SELECT i.id, b.nombre || ' - ' || i.tipo as ref, b.direccion, b.barrio, b.localidad, 
               i.tipo, i.precio_alquiler, i.costo_contrato, i.deposito_base 
        FROM inmuebles i JOIN bloques b ON i.id_bloque=b.id
    """)
    i_df = db_query("SELECT id, nombre, dni, celular FROM inquilinos")
    
    if u_df is not None and i_df is not None and not u_df.empty:
        # --- PASO 1: SELECCIÓN (Fuera del Form para reactividad) ---
        st.subheader("1. Selección de Unidad e Inquilino")
        c_sel1, c_sel2 = st.columns(2)
        
        uid = c_sel1.selectbox("Seleccione Unidad", u_df['id'], 
                               format_func=lambda x: u_df[u_df['id']==x]['ref'].values[0])
        
        iid = c_sel2.selectbox("Seleccione Inquilino", i_df['id'], 
                               format_func=lambda x: i_df[i_df['id']==x]['nombre'].values[0])
        
        # Obtenemos datos de la unidad elegida para precargar montos
        sel_u = u_df[u_df['id'] == uid].iloc[0]
        sel_inq = i_df[i_df['id'] == iid].iloc[0]

        st.write("---")
        
        # --- PASO 2: FORMULARIO DE CONTRATO ---
        st.subheader("2. Condiciones del Contrato")
        with st.form("f_contrato_final", clear_on_submit=True):
            col1, col2 = st.columns(2)
            
            fini = col1.date_input("Fecha de Inicio", date.today())
            meses = col2.number_input("Duración (Meses)", min_value=1, max_value=60, value=6)
            
            st.markdown("**Valores Económicos (Editables):**")
            c_m1, c_m2, c_m3 = st.columns(3)
            ma = c_m1.text_input("Alquiler Mensual", f_m(sel_u['precio_alquiler']))
            md = c_m2.text_input("Depósito Garantía", f_m(sel_u['deposito_base']))
            mc = c_m3.text_input("Gasto Administrativo", f_m(sel_u['costo_contrato']))
            
            # BOTÓN DE GRABAR
            if st.form_submit_button("✅ GRABAR Y GENERAR PDF"):
                # A. CONTROL ANTI-DUPLICADOS (Verificamos si sigue libre)
                check = db_query("SELECT id FROM contratos WHERE id_inmueble=? AND activo=1", (uid,))
                
                if check is not None and not check.empty:
                    st.error("🚫 ERROR: Esta unidad ya fue alquilada recientemente. Operación cancelada.")
                else:
                    try:
                        # B. CÁLCULO DE FIN Y GRABACIÓN
                        f_vence = fini + timedelta(days=meses * 30)
                        
                        nuevo_cid = db_query("""
                            INSERT INTO contratos (id_inmueble, id_inquilino, fecha_inicio, fecha_fin, monto_alquiler, activo) 
                            VALUES (?, ?, ?, ?, ?, 1)
                        """, (int(uid), int(iid), fini, f_vence, cl(ma)), commit=True)

                        # C. GENERACIÓN DE DEUDAS INICIALES
                        db_query("INSERT INTO deudas (id_contrato, concepto, monto_debe, pagado) VALUES (?, 'Mes 1 Alquiler', ?, 0)", (nuevo_cid, cl(ma)), commit=True)
                        db_query("INSERT INTO deudas (id_contrato, concepto, monto_debe, pagado) VALUES (?, 'Garantía/Depósito', ?, 0)", (nuevo_cid, cl(md)), commit=True)
                        db_query("INSERT INTO deudas (id_contrato, concepto, monto_debe, pagado) VALUES (?, 'Gastos Administrativos', ?, 0)", (nuevo_cid, cl(mc)), commit=True)

                        # D. PREPARACIÓN DEL PDF (Persistencia en Session State)
                        pdf_bytes = generar_pdf_v5(sel_u, sel_inq, fini, ma, md, mc)
                        st.session_state['pdf_contrato'] = bytes(pdf_bytes)
                        st.session_state['nro_contrato'] = nuevo_cid
                        
                        st.success(f"🎉 Contrato #{nuevo_cid} registrado con éxito.")
                        st.rerun() # Limpia el form y actualiza la vista

                    except Exception as e:
                        st.error(f"Error técnico al grabar: {e}")

    # --- PASO 3: DESCARGA (Fuera del form para que persista) ---
    if 'pdf_contrato' in st.session_state:
        st.write("---")
        st.subheader("📄 Descarga de Documento")
        c_d1, c_d2 = st.columns([2, 1])
        
        c_d1.download_button(
            label=f"📥 DESCARGAR CONTRATO #{st.session_state.get('nro_contrato')}",
            data=st.session_state['pdf_contrato'],
            file_name=f"Contrato_NL_{st.session_state.get('nro_contrato')}.pdf",
            mime="application/pdf"
        )
        
        if c_d2.button("Limpiar Pantalla"):
            del st.session_state['pdf_contrato']
            st.rerun()

    else:
        st.warning("Debe tener Unidades e Inquilinos cargados en 'Maestros' para operar.")

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

# --- FUNCIONALIDAD: ELIMINAR DEUDA ERRÓNEA ---
    st.write("---")
    with st.expander("🗑️ Zona de Corrección: Eliminar Deuda Errónea"):
        st.info("Use esta opción solo para borrar deudas generadas por error. No la use para registrar cobros.")
        
        # Obtenemos la lista de deudas PENDIENTES para elegir cuál borrar
        df_pendientes = db_query("""
            SELECT d.id, inq.nombre || ' - ' || d.concepto as Ref
            FROM deudas d
            JOIN contratos c ON d.id_contrato = c.id
            JOIN inquilinos inq ON c.id_inquilino = inq.id
            WHERE d.pagado = 0
        """)
        
        if df_pendientes is not None and not df_pendientes.empty:
            sel_deuda_borrar = st.selectbox(
                "Seleccione la deuda a ELIMINAR PERMANENTEMENTE:",
                df_pendientes['id'].tolist(),
                format_func=lambda x: df_pendientes[df_pendientes['id']==x]['Ref'].values[0]
            )
            
            confirmar_borrado = st.checkbox("Confirmo que deseo eliminar este registro permanentemente.")
            
            if st.button("❌ ELIMINAR REGISTRO"):
                if confirmar_borrado:
                    db_query("DELETE FROM deudas WHERE id=?", (sel_deuda_borrar,), commit=True)
                    st.success("Registro eliminado de la base de datos.")
                    st.rerun()
                else:
                    st.warning("Debe marcar el cuadro de confirmación para proceder.")
        else:
            st.write("No hay deudas pendientes registradas.")        
        
# ==========================================
# --- SECCIÓN MOROSOS CORREGIDA ---
elif menu == "🚨 Morosos":

    st.subheader("Morosos")

    query_morosos = """
        SELECT inq.nombre, d.monto_debe 
        FROM deudas d 
        JOIN contratos c ON d.id_contrato = c.id 
        JOIN inquilinos inq ON c.id_inquilino = inq.id 
        WHERE d.pagado = 0
    """
    df_morosos = db_query(query_morosos)

    if df_morosos is not None and not df_morosos.empty:
        # 1. Creamos una copia para no alterar los datos originales si necesitás sumar
        df_morosos_view = df_morosos.copy()
    
        # 2. Aplicamos el formato: Sin decimales y con punto en miles
        df_morosos_view['monto_debe'] = df_morosos_view['monto_debe'].apply(f_m)
    
        # 3. Mostramos la tabla limpia
        st.dataframe(df_morosos_view, use_container_width=True, hide_index=True)
    else:
        st.success("✅ ¡No hay morosos registrados!")


# ==========================================
# 4. CONTROL DE CAJA (V.11.2 - INDEPENDIENTE)
# ==========================================
elif menu == "📊 Caja":
    st.header("Historial de Ingresos y Control de Caja")

    # 1. FILTROS DE TIEMPO
    c1, c2 = st.columns([2, 1])
    with c1:
        filtro_caja = st.radio(
            "Visualizar ingresos de:",
            ["Hoy", "Este Mes", "Este Año", "Total Histórico"],
            horizontal=True
        )
    
    # Lógica de fechas para la consulta SQL
    hoy = date.today()
    if filtro_caja == "Hoy":
        condicion = f"d.fecha_pago = '{hoy}'"
    elif filtro_caja == "Este Mes":
        condicion = f"strftime('%m', d.fecha_pago) = '{hoy.strftime('%m')}' AND strftime('%Y', d.fecha_pago) = '{hoy.strftime('%Y')}'"
    elif filtro_caja == "Este Año":
        condicion = f"strftime('%Y', d.fecha_pago) = '{hoy.strftime('%Y')}'"
    else:
        condicion = "d.pagado = 1"

    # 2. CONSULTA A LA BASE DE DATOS
    query_caja = f"""
        SELECT 
            d.id as [ID Reg],
            inq.nombre as Inquilino,
            b.nombre || ' - ' || i.tipo as Unidad,
            d.concepto as Concepto,
            d.monto_pago as Importe,
            d.fecha_pago as [Fecha]
        FROM deudas d
        JOIN contratos c ON d.id_contrato = c.id
        JOIN inmuebles i ON c.id_inmueble = i.id
        JOIN bloques b ON i.id_bloque = b.id
        JOIN inquilinos inq ON c.id_inquilino = inq.id
        WHERE d.pagado = 1 AND {condicion}
        ORDER BY d.fecha_pago DESC
    """
    df_caja = db_query(query_caja)

    if df_caja is not None and not df_caja.empty:
        # 3. MÉTRICAS Y EXPORTACIÓN
        total_recaudado = df_caja['Importe'].sum()
        
        m1, m2 = st.columns([2, 1])
        m1.metric(f"💰 TOTAL RECAUDADO ({filtro_caja})", f"$ {f_m(total_recaudado)}")
        
        # Botón de Exportar a Excel
        output_excel = io.BytesIO()
        with pd.ExcelWriter(output_excel, engine='xlsxwriter') as writer:
            df_caja.to_excel(writer, sheet_name='Caja', index=False)
        
        m2.write(" ") # Espaciador
        m2.download_button(
            label="📥 Exportar Excel",
            data=output_excel.getvalue(),
            file_name=f"Caja_{filtro_caja}_{hoy}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

        st.write("---")

        # 4. VISUALIZACIÓN DE LA TABLA (Ocultando ID para estética)
        st.dataframe(df_caja.drop(columns=['[ID Reg]']), use_container_width=True, hide_index=True)

        # 5. ELIMINAR REGISTRO (CORRECCIÓN)
        with st.expander("🛠️ Corregir error en Caja (Anular Pago)"):
            st.warning("Al eliminar un registro, la deuda volverá a figurar como PENDIENTE.")
            id_borrar = st.selectbox("Seleccione el ID de registro a anular", df_caja['[ID Reg]'].tolist())
            
            if st.button("❌ ANULAR PAGO"):
                # No borramos la fila, solo "des-pagamos" para que el inquilino deba de nuevo
                db_query(
                    "UPDATE deudas SET pagado=0, monto_pago=0, fecha_pago=NULL WHERE id=?", 
                    (id_borrar,), 
                    commit=True
                )
                st.success(f"Registro {id_borrar} anulado. La deuda vuelve a estar pendiente.")
                st.rerun()
    else:
        st.info(f"Sin movimientos registrados para el período: {filtro_caja}")

        
# ==========================================
# 6. MAESTROS (V.8.6 - EDICIÓN Y BAJA RESTAURADAS)
# ==========================================
elif menu == "⚙️ Maestros":
    st.header("Administración de Base de Datos")
    
    t1, t2, t3, t4, t5, t6, t7 = st.tabs([
        "🏢 Inmuebles", "🏠 Unidades", "👤 Inquilinos", 
        "📋 Contratos", "💾 Backup", "📋 Alquilados", "⚙️ Generación Mensual"
    ])

    # --- 1. INMUEBLES ---
    with t1:
        st.subheader("Edificios y Complejos")
        df_inm = db_query("SELECT id, nombre, direccion, barrio, localidad FROM bloques")
        
        with st.expander("➕ Cargar Nuevo Inmueble"):
            with st.form("f_inm_alta", clear_on_submit=True):
                c1, c2 = st.columns(2)
                n = c1.text_input("Nombre del Edificio")
                d = c1.text_input("Dirección")
                b = c2.text_input("Barrio")
                l = c2.text_input("Localidad")
                if st.form_submit_button("Guardar"):
                    db_query("INSERT INTO bloques (nombre, direccion, barrio, localidad) VALUES (?,?,?,?)", (n, d, b, l), commit=True)
                    st.rerun()
        
        if df_inm is not None and not df_inm.empty:
            st.dataframe(df_inm.drop(columns=['id']), use_container_width=True, hide_index=True)
            st.write("---")
            # SECCIÓN EDICIÓN/BORRADO
            sel_inm_nom = st.selectbox("Seleccione Inmueble para gestionar", df_inm['nombre'].tolist())
            dat_inm = df_inm[df_inm['nombre'] == sel_inm_nom].iloc[0]
            
            with st.form("f_inm_edit"):
                c1, c2 = st.columns(2)
                en_n = c1.text_input("Nombre", dat_inm['nombre'])
                en_d = c1.text_input("Dirección", dat_inm['direccion'])
                en_b = c2.text_input("Barrio", dat_inm['barrio'])
                en_l = c2.text_input("Localidad", dat_inm['localidad'])
                
                col_b1, col_b2 = st.columns(2)
                if col_b1.form_submit_button("💾 Actualizar Inmueble"):
                    db_query("UPDATE bloques SET nombre=?, direccion=?, barrio=?, localidad=? WHERE id=?", (en_n, en_d, en_b, en_l, int(dat_inm['id'])), commit=True)
                    st.rerun()
                if col_b2.form_submit_button("🗑️ ELIMINAR"):
                    db_query(f"DELETE FROM bloques WHERE id={int(dat_inm['id'])}", commit=True)
                    st.rerun()

    # --- 2. UNIDADES ---
    with t2:
        st.subheader("Gestión de Unidades")
        df_b_ref = db_query("SELECT id, nombre FROM bloques")
        df_uni = db_query("""SELECT i.id, b.nombre as Inmueble, i.tipo as Unidad, 
                             i.precio_alquiler as Alquiler, i.costo_contrato as Contrato, 
                             i.deposito_base as Deposito, i.id_bloque
                             FROM inmuebles i JOIN bloques b ON i.id_bloque = b.id""")

        if df_b_ref is not None and not df_b_ref.empty:
            with st.expander("➕ Cargar Nueva Unidad"):
                with st.form("f_u_alta", clear_on_submit=True):
                    bid = st.selectbox("Inmueble", df_b_ref['id'], format_func=lambda x: df_b_ref[df_b_ref['id']==x]['nombre'].values[0])
                    tipo = st.text_input("Descripción Unidad")
                    c1, c2, c3 = st.columns(3)
                    p1 = c1.text_input("Alquiler")
                    p2 = c2.text_input("Contrato")
                    p3 = c3.text_input("Deposito")
                    if st.form_submit_button("Crear"):
                        db_query("INSERT INTO inmuebles (id_bloque, tipo, precio_alquiler, costo_contrato, deposito_base) VALUES (?,?,?,?,?)", (bid, tipo, cl(p1), cl(p2), cl(p3)), commit=True)
                        st.rerun()
            
            if df_uni is not None and not df_uni.empty:
                df_u_show = df_uni.drop(columns=['id', 'id_bloque']).copy()
                for col in ['Alquiler', 'Contrato', 'Deposito']: df_u_show[col] = df_u_show[col].apply(f_m)
                st.dataframe(df_u_show, use_container_width=True, hide_index=True)
                
                st.write("---")
                sel_u_ref = st.selectbox("Seleccione Unidad para gestionar", df_uni.index.tolist(), format_func=lambda x: f"{df_uni.loc[x, 'Inmueble']} - {df_uni.loc[x, 'Unidad']}")
                dat_u = df_uni.loc[sel_u_ref]
                
                with st.form("f_u_edit"):
                    c1, c2, c3 = st.columns(3)
                    eu_t = st.text_input("Descripción", dat_u['Unidad'])
                    eu_a = c1.text_input("Alquiler", f_m(dat_u['Alquiler']))
                    eu_c = c2.text_input("Contrato", f_m(dat_u['Contrato']))
                    eu_d = c3.text_input("Deposito", f_m(dat_u['Deposito']))
                    
                    cb1, cb2 = st.columns(2)
                    if cb1.form_submit_button("💾 Actualizar Unidad"):
                        db_query("UPDATE inmuebles SET tipo=?, precio_alquiler=?, costo_contrato=?, deposito_base=? WHERE id=?", (eu_t, cl(eu_a), cl(eu_c), cl(eu_d), int(dat_u['id'])), commit=True)
                        st.rerun()
                    if cb2.form_submit_button("🗑️ ELIMINAR"):
                        db_query(f"DELETE FROM inmuebles WHERE id={int(dat_u['id'])}", commit=True)
                        st.rerun()

    # --- 3. INQUILINOS --- (Se mantiene Domicilio y Edición)
    with t3:
        st.subheader("Registro de Inquilinos")
        df_inq = db_query("SELECT id, nombre, dni, celular, procedencia, grupo, emergencia FROM inquilinos")
        
        with st.expander("➕ Cargar Nuevo Inquilino"):
            with st.form("f_inq_alta", clear_on_submit=True):
                c1, c2 = st.columns(2)
                n = c1.text_input("Nombre y Apellido")
                dni = c1.text_input("DNI / CUIT")
                cel = c1.text_input("WhatsApp")
                dom = c2.text_input("Domicilio")
                gru = c2.text_input("Grupo")
                eme = c2.text_input("Emergencia")
                if st.form_submit_button("Guardar Inquilino"):
                    db_query("INSERT INTO inquilinos (nombre, dni, celular, procedencia, grupo, emergencia) VALUES (?,?,?,?,?,?)", (n, dni, cel, dom, gru, eme), commit=True)
                    st.rerun()
        
        if df_inq is not None and not df_inq.empty:
            df_inq_v = df_inq.rename(columns={'procedencia': 'Domicilio'}).drop(columns=['id'])
            st.dataframe(df_inq_v, use_container_width=True, hide_index=True)
            
            st.write("---")
            sel_inq_nom = st.selectbox("Seleccione Inquilino para gestionar", df_inq['nombre'].tolist())
            i_dat = df_inq[df_inq['nombre'] == sel_inq_nom].iloc[0]
            
            with st.form("f_inq_edit"):
                c1, c2 = st.columns(2)
                en_n = c1.text_input("Nombre", i_dat['nombre'])
                en_d = c1.text_input("DNI", i_dat['dni'])
                en_c = c1.text_input("WhatsApp", i_dat['celular'])
                en_p = c2.text_input("Domicilio", i_dat['procedencia'])
                en_g = c2.text_input("Grupo", i_dat['grupo'])
                en_e = c2.text_input("Emergencia", i_dat['emergencia'])
                
                col_i1, col_i2 = st.columns(2)
                if col_i1.form_submit_button("💾 Actualizar"):
                    db_query("UPDATE inquilinos SET nombre=?, dni=?, celular=?, procedencia=?, grupo=?, emergencia=? WHERE id=?", (en_n, en_d, en_c, en_p, en_g, en_e, int(i_dat['id'])), commit=True)
                    st.rerun()
                if col_i2.form_submit_button("🗑️ BORRAR"):
                    db_query(f"DELETE FROM inquilinos WHERE id={int(i_dat['id'])}", commit=True)
                    st.rerun()


# --- 4. CONTRATOS (V.9.5 - RENOVACIÓN CON CONTINUIDAD Y PDF) ---
    with t4:
        st.subheader("Gestión de Contratos Vigentes")
        
        query_cont = """
            SELECT 
                c.id as ID_Contrato, b.nombre as Inmueble, i.tipo as Unidad, 
                inq.nombre as Inquilino, c.fecha_inicio as Inicio, c.fecha_fin as Fin,
                c.monto_alquiler as [Alq_Actual], i.precio_alquiler as Alq_Maestro,
                i.costo_contrato as Con_Maestro, i.deposito_base as Dep_Maestro,
                c.id_inmueble, c.id_inquilino
            FROM contratos c 
            INNER JOIN inmuebles i ON c.id_inmueble = i.id 
            INNER JOIN bloques b ON i.id_bloque = b.id 
            INNER JOIN inquilinos inq ON c.id_inquilino = inq.id 
            WHERE c.activo = 1
        """
        df_cont = db_query(query_cont)
        
        if df_cont is not None and not df_cont.empty:
            df_display = df_cont[['ID_Contrato', 'Inmueble', 'Unidad', 'Inquilino', 'Inicio', 'Fin', 'Alq_Actual']].copy()
            st.dataframe(df_display, use_container_width=True, hide_index=True)
            
            st.write("---")
            c1, c2 = st.columns(2)
            sel_c_id = c1.selectbox("Seleccione ID de Contrato", df_cont['ID_Contrato'].tolist())
            row_sel = df_cont[df_cont['ID_Contrato'] == sel_c_id].iloc[0]
            
            if c1.button("🚨 FINALIZAR CONTRATO"):
                db_query(f"UPDATE contratos SET activo=0 WHERE id={sel_c_id}", commit=True)
                st.rerun()
            
            with c2:
                st.markdown("**🔄 Renovar con Continuidad**")
                meses_r = st.number_input("Meses a renovar", min_value=1, value=6, key="r_meses")
                
                if st.button("🚀 EJECUTAR RENOVACIÓN Y PDF"):
                    try:
                        # 1. LÓGICA DE FECHAS: Continuidad absoluta
                        # El nuevo inicia el día después del fin del anterior
                        f_fin_anterior = pd.to_datetime(row_sel['Fin']).date()
                        f_ini_n = f_fin_anterior + timedelta(days=1)
                        f_fin_n = f_ini_n + timedelta(days=meses_r * 30)
                        
                        # 2. Transacción: Baja del viejo y Alta del nuevo
                        db_query(f"UPDATE contratos SET activo=0 WHERE id={sel_c_id}", commit=True)
                        
                        nuevo_id = db_query("""
                            INSERT INTO contratos (id_inmueble, id_inquilino, fecha_inicio, fecha_fin, monto_alquiler, activo) 
                            VALUES (?,?,?,?,?,1)
                        """, (int(row_sel['id_inmueble']), int(row_sel['id_inquilino']), f_ini_n, f_fin_n, int(row_sel['Alq_Maestro'])), commit=True)
                        
                        # 3. Deudas automáticas
                        db_query("INSERT INTO deudas (id_contrato, concepto, monto_debe, monto_pago, pagado) VALUES (?, 'Alquiler Mes 1 (Renov)', ?, 0, 0)", (nuevo_id, int(row_sel['Alq_Maestro'])), commit=True)
                        db_query("INSERT INTO deudas (id_contrato, concepto, monto_debe, monto_pago, pagado) VALUES (?, 'Depósito (Renov)', ?, 0, 0)", (nuevo_id, int(row_sel['Dep_Maestro'])), commit=True)
                        db_query("INSERT INTO deudas (id_contrato, concepto, monto_debe, monto_pago, pagado) VALUES (?, 'Gasto Contrato (Renov)', ?, 0, 0)", (nuevo_id, int(row_sel['Con_Maestro'])), commit=True)
                        
                        # 4. GENERACIÓN DE PDF INMEDIATA
                        # Obtenemos datos limpios para el PDF
                        u_data = db_query(f"SELECT i.*, b.nombre, b.direccion, b.barrio, b.localidad FROM inmuebles i JOIN bloques b ON i.id_bloque=b.id WHERE i.id={row_sel['id_inmueble']}").iloc[0]
                        inq_data = db_query(f"SELECT * FROM inquilinos WHERE id={row_sel['id_inquilino']}").iloc[0]
                        
                        pdf_bytes = generar_pdf_v5(u_data, inq_data, f_ini_n, f_m(row_sel['Alq_Maestro']), f_m(row_sel['Dep_Maestro']), f_m(row_sel['Con_Maestro']))
                        
                        # Guardamos en session_state para que el botón de descarga aparezca
                        st.session_state['pdf_ready'] = bytes(pdf_bytes)
                        st.session_state['cid_last'] = nuevo_id
                        
                        st.success(f"Renovado. Nuevo Contrato: {nuevo_id} (Inicia: {f_ini_n})")
                        st.rerun() # Recargamos para actualizar la tabla y mostrar el PDF
                        
                    except Exception as e:
                        st.error(f"Error en renovación: {e}")

        # Sección de descarga (se muestra si existe un PDF recién generado)
        if 'pdf_ready' in st.session_state:
            st.write("---")
            st.info(f"📄 PDF del Nuevo Contrato #{st.session_state.get('cid_last')} listo para descargar")
            st.download_button("📥 DESCARGAR CONTRATO RENOVADO", st.session_state['pdf_ready'], f"Renovacion_{st.session_state['cid_last']}.pdf", "application/pdf")
            if st.button("Limpiar Notificación"):
                del st.session_state['pdf_ready']
                st.rerun()



    # --- 5. BACKUP & RESTORE (V.13.0 - BOTÓN DE DESCARGA FIJO) ---
    with t5:
        st.subheader("💾 Centro de Datos y Seguridad")
        c_exp, c_imp, c_res = st.columns(3)
        
        with c_exp:
            st.write("**Exportar Datos**")
            # Paso 1: Generar el archivo
            if st.button("📂 Preparar Archivo de Respaldo"):
                try:
                    output = io.BytesIO()
                    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                        # Tablas a exportar
                        for tabla, hoja in [('bloques','Inmuebles'), ('inmuebles','Unidades'), 
                                           ('inquilinos','Inquilinos'), ('contratos','Contratos'), 
                                           ('deudas','Deudas')]:
                            df_tmp = db_query(f"SELECT * FROM {tabla}")
                            if df_tmp is not None:
                                df_tmp.to_excel(writer, sheet_name=hoja, index=False)
                    
                    # Guardamos el binario en el estado de la sesión
                    st.session_state['archivo_backup'] = output.getvalue()
                    st.success("✅ Archivo preparado con éxito.")
                except Exception as e:
                    st.error(f"Error al preparar backup: {e}")

            # Paso 2: Mostrar el botón de descarga si el archivo existe en memoria
            if 'archivo_backup' in st.session_state:
                st.download_button(
                    label="📥 DESCARGAR EXCEL",
                    data=st.session_state['archivo_backup'],
                    file_name=f"Backup_Inmobiliaria_{date.today()}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key="btn_descarga_final"
                )
                if st.button("Limpiar descarga", key="clear_bak"):
                    del st.session_state['archivo_backup']
                    st.rerun()

        with c_imp:
            st.write("**Restaurar Datos**")
            archivo_subido = st.file_uploader("Subir backup (.xlsx)", type=["xlsx"])
            if archivo_subido:
                if st.button("🚀 Ejecutar Restauración"):
                    try:
                        dfs = pd.read_excel(archivo_subido, sheet_name=None)
                        mapping = {'Inmuebles':'bloques', 'Unidades':'inmuebles', 
                                   'Inquilinos':'inquilinos', 'Contratos':'contratos', 'Deudas':'deudas'}
                        with sqlite3.connect('datos_alquileres.db') as conn:
                            for hoja, tabla in mapping.items():
                                if hoja in dfs:
                                    conn.execute(f"DELETE FROM {tabla}")
                                    dfs[hoja].to_sql(tabla, conn, if_exists='append', index=False)
                        st.success("✅ Sistema restaurado correctamente.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error en restauración: {e}")

        with c_res:
            st.write("**Zona de Peligro**")
            cod_m = st.text_input("Código Maestro", type="password", key="pwd_reset")
            if st.button("🔥 RESET SISTEMA"):
                if cod_m == "3280":
                    with sqlite3.connect('datos_alquileres.db') as conn:
                        for t in ['bloques','inmuebles','inquilinos','contratos','deudas']:
                            conn.execute(f"DELETE FROM {t}")
                    st.warning("Base de datos vaciada por completo.")
                    st.rerun()
                else:
                    st.error("Código Maestro incorrecto.")

    # --- 6. LISTADO DE ALQUILADOS ---
    with t6:
        st.subheader("📋 Ocupación Actual")
        df_alq = db_query("""
            SELECT b.nombre as Inmueble, i.tipo as Unidad, inq.nombre as Inquilino, inq.procedencia as Domicilio, inq.celular as [WhatsApp],
                   IFNULL((SELECT SUM(monto_debe - monto_pago) FROM deudas WHERE id_contrato = c.id AND pagado = 0), 0) as Saldo
            FROM contratos c JOIN inmuebles i ON c.id_inmueble = i.id JOIN bloques b ON i.id_bloque = b.id JOIN inquilinos inq ON c.id_inquilino = inq.id
            WHERE c.activo = 1 ORDER BY b.nombre
        """)
        if df_alq is not None and not df_alq.empty:
            df_v = df_alq.copy(); df_v['Saldo'] = df_v['Saldo'].apply(lambda x: f"🔴 ${f_m(x)}" if x > 0 else "🟢 Al día")
            st.dataframe(df_v, use_container_width=True, hide_index=True)
            st.metric("Deuda Total en Calle", f"$ {f_m(df_alq['Saldo'].sum())}")

    # --- 7. GENERACIÓN MENSUAL ---
    with t7:
        st.subheader("⚙️ Generación de Deuda")
        with st.form("f_gen_mas"):
            mes = st.selectbox("Mes", ["Enero","Febrero","Marzo","Abril","Mayo","Junio","Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"])
            anio = st.number_input("Año", value=2026)
            if st.form_submit_button("Ejecutar Generación"):
                conts = db_query("SELECT id, monto_alquiler FROM contratos WHERE activo=1")
                for _, c in conts.iterrows():
                    conc = f"Alquiler {mes} {anio}"
                    if db_query("SELECT id FROM deudas WHERE id_contrato=? AND concepto=?", (int(c['id']), conc)).empty:
                        db_query("INSERT INTO deudas (id_contrato, concepto, monto_debe, monto_pago, pagado) VALUES (?,?,?,0,0)", (int(c['id']), conc, int(c['monto_alquiler'])), commit=True)
                st.success("Cargos generados.")

# ==========================================
# 7. GESTIÓN DE LOTES (V.2.0 - CRUD COMPLETO)
# ==========================================
elif menu == "🌳 Lotes":
    st.header("Gestión y Comercialización de Lotes (U$D)")
    
    # Crear carpeta de fotos si no existe
    if not os.path.exists("fotos_lotes"):
        os.makedirs("fotos_lotes")

    t_l1, t_l2, t_l3, t_l4, t_l5 = st.tabs([
        "🏗️ Desarrollos", "📏 Inventario Lotes", "👤 Compradores", "🤝 Ventas", "💰 Cuotas y Cobros"
    ])

    # --- 1. DESARROLLOS (VERSIÓN DE PRUEBA RÍGIDA) ---
    with t_l1:
        st.subheader("Configuración de Loteos")
        
        # Formulario de Carga
        with st.form("f_nuevo_loteo", clear_on_submit=True):
            n_name = st.text_input("Nombre del Barrio / Desarrollo")
            n_ubica = st.text_input("Ubicación Exacta")
            n_local = st.text_input("Localidad")
            
            submit_loteo = st.form_submit_button("💾 GRABAR AHORA")
            
        if submit_loteo:
            if n_name:
                res = db_query("INSERT INTO desarrollos (nombre, ubicacion, localidad) VALUES (?,?,?)", 
                               (n_name, n_ubica, n_local), commit=True)
                if res:
                    st.success(f"✅ ¡Guardado con éxito! ID generado: {res}")
                    st.rerun()
            else:
                st.warning("Por favor, ingresá al menos el nombre.")

        st.write("---")
        st.write("**Listado Actual en Base de Datos:**")
        
        # Forzamos la lectura limpia
        df_listado = db_query("SELECT id, nombre, ubicacion, localidad FROM desarrollos")
        
        if df_listado is not None and not df_listado.empty:
            st.table(df_listado) # Usamos st.table que es más rígido que dataframe para probar
            
            # Botón de borrado rápido para limpieza
            id_borrar = st.number_input("ID para eliminar", min_value=1, step=1)
            if st.button("🗑️ Eliminar Registro"):
                db_query(f"DELETE FROM desarrollos WHERE id={id_borrar}", commit=True)
                st.rerun()
        else:
            st.info("La base de datos de desarrollos está vacía.")

# --- 2. INVENTARIO DE LOTES (CON ESTRUCTURA DE FINANCIACIÓN) ---
    with t_l2:
        st.subheader("Gestión de Lotes e Imágenes")
        
        df_d_ref = db_query("SELECT id, nombre FROM desarrollos")
        if df_d_ref is not None and not df_d_ref.empty:
            with st.expander("🛠️ Panel de Carga y Edición de Lote", expanded=True):
                with st.form("f_lote_abm_v2", clear_on_submit=True):
                    id_l_e = st.number_input("ID Lote para editar (0 para nuevo)", min_value=0, value=0)
                    id_d = st.selectbox("Desarrollo", df_d_ref['id'], format_func=lambda x: df_d_ref[df_d_ref['id']==x]['nombre'].values[0])
                    
                    c1, c2, c3 = st.columns(3)
                    mz = c1.text_input("Manzana")
                    lt = c2.text_input("Nro Lote")
                    m2 = c3.number_input("M2 Totales", min_value=0.0)
                    
                    f1, f2, f3 = st.columns(3)
                    fre = f1.number_input("Metros Frente", min_value=0.0)
                    fon = f2.number_input("Metros Fondo", min_value=0.0)
                    serv = f3.multiselect("Servicios", ["LUZ", "AGUA", "INTERNET", "GAS"])
                    
                    st.markdown("---")
                    st.markdown("**💰 Propuesta Comercial (U$D)**")
                    p1, p2, p3, p4 = st.columns(4)
                    p_cont = p1.number_input("Precio Contado", min_value=0, step=1, format="%d")
                    p_entrega = p2.number_input("Entrega Sugerida", min_value=0, step=1, format="%d")
                    p_cuotas_n = p3.number_input("Cant. Cuotas", min_value=0, value=12)
                    p_cuota_v = p4.number_input("Valor Cuota", min_value=0, step=1, format="%d")

                    obs = st.text_area("Observaciones")
                    fotos = st.file_uploader("Subir Imágenes del Lote", accept_multiple_files=True, type=['jpg','png','jpeg'])
                    
                    if st.form_submit_button("💾 GUARDAR LOTE"):
                        serv_str = ", ".join(serv)
                        # Cálculo del "Precio Financiado" total para la base de datos
                        p_fin_total = p_entrega + (p_cuotas_n * p_cuota_v)
                        
                        if id_l_e == 0:
                            # INSERT: Asegurate de que tu tabla tenga las columnas o usaremos precio_financiado para el total
                            new_id = db_query("""INSERT INTO lotes 
                                (id_desarrollo, manzana, nro_lote, metros_cuadrados, frente, fondo, servicios, observaciones, precio_contado, precio_financiado) 
                                VALUES (?,?,?,?,?,?,?,?,?,?)""", 
                                (id_d, mz, lt, m2, fre, fon, serv_str, obs, p_cont, p_fin_total), commit=True)
                            target_id = new_id
                        else:
                            # UPDATE
                            db_query("""UPDATE lotes SET 
                                id_desarrollo=?, manzana=?, nro_lote=?, metros_cuadrados=?, frente=?, fondo=?, servicios=?, observaciones=?, precio_contado=?, precio_financiado=? 
                                WHERE id=?""", 
                                (id_d, mz, lt, m2, fre, fon, serv_str, obs, p_cont, p_fin_total, id_l_e), commit=True)
                            target_id = id_l_e
                        
                        # Guardar fotos
                        if fotos:
                            for i, foto in enumerate(fotos):
                                with open(f"fotos_lotes/lote_{target_id}_{i}.jpg", "wb") as f:
                                    f.write(foto.getbuffer())
                        
                        st.success(f"✅ Lote {target_id} guardado con éxito.")
                        st.rerun()

            # --- Visualización con las nuevas columnas ---
            st.write("---")
            df_lotes = db_query("""
                SELECT l.id as ID, d.nombre as Desarrollo, l.manzana as Mz, l.nro_lote as Lote, 
                       l.estado as Estado, l.precio_contado as [Contado U$D], 
                       l.precio_financiado as [Total Financiado U$D]
                FROM lotes l 
                JOIN desarrollos d ON l.id_desarrollo = d.id
            """)
            
            if df_lotes is not None:
                st.dataframe(df_lotes, use_container_width=True, hide_index=True)
                
                # Visualizador de fotos y eliminación (se mantiene igual)
                c_v1, c_v2 = st.columns([2,1])
                sel_v = c_v1.selectbox("Acciones para Lote ID:", df_lotes['ID'].tolist())
                
                galeria = [f"fotos_lotes/{img}" for img in os.listdir("fotos_lotes") if img.startswith(f"lote_{sel_v}_")]
                if galeria:
                    st.image(galeria, width=150)
                
                if c_v2.button("🗑️ ELIMINAR LOTE"):
                    db_query(f"DELETE FROM lotes WHERE id={sel_v}", commit=True)
                    st.rerun()


    # --- 3. COMPRADORES (ABM) ---
    with t_l3:
        st.subheader("Gestión de Compradores")
        with st.expander("👤 Nuevo / Editar Comprador"):
            with st.form("f_comp_edit"):
                id_c_e = st.number_input("ID para editar (0 para nuevo)", min_value=0)
                nom = st.text_input("Nombre Completo")
                doc = st.text_input("DNI / CUIT")
                cel = st.text_input("Celular")
                if st.form_submit_button("Guardar Comprador"):
                    if id_c_e == 0:
                        db_query("INSERT INTO compradores (nombre, dni_cuit, celular) VALUES (?,?,?)", (nom, doc, cel), commit=True)
                    else:
                        db_query("UPDATE compradores SET nombre=?, dni_cuit=?, celular=? WHERE id=?", (nom, doc, cel, id_c_e), commit=True)
                    st.rerun()
        
        df_c = db_query("SELECT * FROM compradores")
        if df_c is not None:
            st.dataframe(df_c, hide_index=True)
            id_c_del = st.number_input("ID Comprador a eliminar", min_value=0)
            if st.button("🗑️ Eliminar Comprador"):
                db_query(f"DELETE FROM compradores WHERE id={id_c_del}", commit=True)
                st.rerun()


    # --- 4. VENTAS ---
    with t_l4:
        st.subheader("Registrar Venta de Lote")
        lotes_libres = db_query("SELECT id, manzana || '-' || nro_lote as ref FROM lotes WHERE estado='Libre'")
        comps = db_query("SELECT id, nombre FROM compradores")
        
        if lotes_libres is not None and comps is not None:
            with st.form("f_venta_lote"):
                id_l = st.selectbox("Lote a vender", lotes_libres['id'], format_func=lambda x: lotes_libres[lotes_libres['id']==x]['ref'].values[0])
                id_c = st.selectbox("Comprador", comps['id'], format_func=lambda x: comps[comps['id']==x]['nombre'].values[0])
                c1, c2, c3 = st.columns(3)
                tot_usd = c1.number_input("Precio Venta Total (U$D)")
                ent_usd = c2.number_input("Entrega Inicial (U$D)")
                cuotas = c3.number_input("Cantidad de Cuotas", min_value=0, value=12)
                f_v = st.date_input("Fecha de Operación")
                
                if st.form_submit_button("🤝 CONFIRMAR VENTA"):
                    # 1. Registrar Venta
                    monto_cuota = (tot_usd - ent_usd) / cuotas if cuotas > 0 else 0
                    v_id = db_query("""INSERT INTO ventas_lotes (id_lote, id_comprador, fecha_venta, monto_total_usd, entrega_usd, cantidad_cuotas, monto_cuota_usd) 
                                    VALUES (?,?,?,?,?,?,?)""", (id_l, id_c, f_v, tot_usd, ent_usd, cuotas, monto_cuota), commit=True)
                    
                    # 2. Generar Cuotas
                    for i in range(1, cuotas + 1):
                        venc = f_v + timedelta(days=30 * i)
                        db_query("INSERT INTO cuotas_lotes (id_venta, nro_cuota, monto_usd, fecha_vencimiento) VALUES (?,?,?,?)", (v_id, i, monto_cuota, venc), commit=True)
                    
                    # 3. Marcar lote como vendido
                    db_query(f"UPDATE lotes SET estado='Vendido' WHERE id={id_l}", commit=True)
                    st.success("Venta registrada y plan de cuotas generado.")
                    st.rerun()

# --- 5. COBRANZAS Y RECIBOS (V.1.2 - CON PDF U$D) ---
    with t_l5:
        st.subheader("Cobranza de Cuotas y Entregas (U$D)")
        
        query_pend = """
            SELECT cl.id, co.nombre as Comprador, l.manzana, l.nro_lote, 
                   cl.nro_cuota, cl.monto_usd, vl.id_lote, vl.id_comprador
            FROM cuotas_lotes cl
            JOIN ventas_lotes vl ON cl.id_venta = vl.id
            JOIN compradores co ON vl.id_comprador = co.id
            JOIN lotes l ON vl.id_lote = l.id
            WHERE cl.pagado = 0
        """
        df_p = db_query(query_pend)
        
        if df_p is not None and not df_p.empty:
            with st.form("f_cobro_lote_pdf"):
                sel_id = st.selectbox("Seleccione cuota a cobrar", df_p['id'].tolist(), 
                                      format_func=lambda x: f"{df_p[df_p['id']==x]['Comprador'].values[0]} - Mz {df_p[df_p['id']==x]['manzana'].values[0]} Lote {df_p[df_p['id']==x]['nro_lote'].values[0]} - Cuota {df_p[df_p['id']==x]['nro_cuota'].values[0]}")
                
                row_p = df_p[df_p['id'] == sel_id].iloc[0]
                m_cobro = st.number_input("Confirmar Monto U$D", value=float(row_p['monto_usd']))
                
                if st.form_submit_button("✅ COBRAR Y GENERAR RECIBO"):
                    # 1. Update en DB
                    db_query("UPDATE cuotas_lotes SET pagado=1, monto_pagado_usd=?, fecha_pago=? WHERE id=?", (m_cobro, date.today(), sel_id), commit=True)
                    
                    # 2. Datos para el PDF
                    datos_p = {'monto': m_cobro, 'concepto': f"Cuota Nro {row_p['nro_cuota']}"}
                    datos_c = {'nombre': row_p['Comprador']}
                    datos_l = {'manzana': row_p['manzana'], 'nro_lote': row_p['nro_lote']}
                    
                    # 3. Generar y persistir
                    pdf_lote = generar_pdf_lote(datos_p, datos_c, datos_l)
                    st.session_state['pdf_lote_ready'] = bytes(pdf_lote)
                    st.success("¡Cobro registrado con éxito!")
                    st.rerun()

        # Botón de descarga fuera del form
        if 'pdf_lote_ready' in st.session_state:
            st.write("---")
            st.download_button(
                label="📥 DESCARGAR RECIBO U$D",
                data=st.session_state['pdf_lote_ready'],
                file_name=f"Recibo_Lote_{date.today()}.pdf",
                mime="application/pdf"
            )
            if st.button("Limpiar"):
                del st.session_state['pdf_lote_ready']
                st.rerun()


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
