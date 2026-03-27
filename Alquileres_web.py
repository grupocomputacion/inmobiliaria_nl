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

# ==========================================
# 1. INVENTARIO (V.3.1 - ESTADO Y DISPONIBILIDAD)
# ==========================================
if menu == "🏠 Inventario":
    st.header("Disponibilidad y Valores de Unidades")
    
    # Query optimizada: quitamos dirección y sumamos contrato/depósito
    query_inv = """
        SELECT 
            b.nombre as Inmueble, 
            i.tipo as Unidad, 
            i.precio_alquiler as Alquiler,
            i.costo_contrato as Contrato,
            i.deposito_base as [Depósito Sug.],
            CASE 
                WHEN c.activo = 1 THEN '🔴 OCUPADO' 
                ELSE '🟢 LIBRE' 
            END as Estado,
            CASE 
                WHEN c.activo = 1 THEN c.fecha_fin 
                ELSE 'DISPONIBLE HOY' 
            END as [Disponible desde]
        FROM inmuebles i 
        JOIN bloques b ON i.id_bloque = b.id
        LEFT JOIN contratos c ON i.id = c.id_inmueble AND c.activo = 1
    """
    
    df_inv = db_query(query_inv)
    
    if df_inv is not None and not df_inv.empty:
        # Aplicamos formato de miles (punto) a las 3 columnas de dinero
        cols_dinero = ['Alquiler', 'Contrato', 'Depósito Sug.']
        for col in cols_dinero:
            df_inv[col] = df_inv[col].apply(f_m)
            
        # Mostramos la tabla limpia y profesional
        st.dataframe(
            df_inv, 
            use_container_width=True, 
            hide_index=True,
            column_config={
                "Estado": st.column_config.TextColumn("Estado", help="Rojo: Ocupado | Verde: Disponible"),
                "Disponible desde": st.column_config.TextColumn("📅 Disponibilidad")
            }
        )
        
        # Resumen rápido para el cliente
        c1, c2 = st.columns(2)
        libres = len(df_inv[df_inv['Estado'] == '🟢 LIBRE'])
        c1.metric("Unidades Libres", libres)
        c2.metric("Total Unidades", len(df_inv))
        
    else:
        st.info("No hay unidades para mostrar. Cargue datos en la sección Maestros.")

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
