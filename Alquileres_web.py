import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, date, timedelta
import os
import io

# ==========================================
# 1. IDENTIDAD Y CONFIGURACIÓN (V.2.4)
# ==========================================
st.set_page_config(page_title="NL PROPIEDADES - V.2.4", layout="wide")
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

# Inicialización de Tablas
db_query("CREATE TABLE IF NOT EXISTS bloques (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT UNIQUE)", commit=True)
db_query("""CREATE TABLE IF NOT EXISTS inquilinos (
    id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT, dni TEXT, celular TEXT, 
    emergencia TEXT, procedencia TEXT, grupo TEXT)""", commit=True)
db_query("CREATE TABLE IF NOT EXISTS inmuebles (id INTEGER PRIMARY KEY AUTOINCREMENT, id_bloque INTEGER, tipo TEXT, precio_alquiler INTEGER, costo_contrato INTEGER, deposito_base INTEGER)", commit=True)
db_query("CREATE TABLE IF NOT EXISTS contratos (id INTEGER PRIMARY KEY AUTOINCREMENT, id_inmueble INTEGER, id_inquilino INTEGER, fecha_inicio DATE, fecha_fin DATE, monto_alquiler INTEGER, activo INTEGER DEFAULT 1)", commit=True)
db_query("CREATE TABLE IF NOT EXISTS deudas (id INTEGER PRIMARY KEY AUTOINCREMENT, id_contrato INTEGER, concepto TEXT, monto_debe INTEGER, monto_pago INTEGER DEFAULT 0, pagado INTEGER DEFAULT 0, fecha_pago DATE)", commit=True)

# --- FUNCIONES DE FORMATO ---
def cl(t): return int(str(t).replace('$', '').replace('.', '').replace(',', '').strip() or 0)
def f_m(v): return f"{int(v or 0):,}".replace(",", ".")

# ==========================================
# 3. BARRA LATERAL
# ==========================================
with st.sidebar:
    if os.path.exists("alquileres.jpg"): st.image("alquileres.jpg", use_container_width=True)
    else: st.title("🏠 NL PROPIEDADES")
    
    st.info("🚀 VERSIÓN: V.2.4 - REVISIÓN FINAL")
    menu = st.radio("MENÚ:", ["🏠 Inventario", "📝 Nuevo Contrato", "💰 Cobranzas", "🚨 Morosos", "📊 Caja y Reportes", "⚙️ Maestros"])
    
    if st.button("🚨 RESET BASE (CUIDADO)"):
        if os.path.exists('datos_alquileres.db'): os.remove('datos_alquileres.db')
        st.rerun()

# ==========================================
# 4. SECCIONES
# ==========================================

# --- 1. INVENTARIO ---
if menu == "🏠 Inventario":
    st.header("Inventario de Unidades y Disponibilidad")
    query_inv = """
        SELECT b.nombre as Bloque, i.tipo as Unidad, i.precio_alquiler as [Alquiler Sug.],
               i.costo_contrato as [Gasto Cont.], i.deposito_base as [Depósito Sug.],
               CASE WHEN c.activo = 1 THEN '🔴 OCUPADO' ELSE '🟢 LIBRE' END as Estado,
               CASE WHEN c.activo = 1 THEN c.fecha_fin ELSE 'DISPONIBLE HOY' END as [Vence/Libre]
        FROM inmuebles i JOIN bloques b ON i.id_bloque = b.id
        LEFT JOIN contratos c ON i.id = c.id_inmueble AND c.activo = 1
    """
    df = db_query(query_inv)
    if df is not None and not df.empty:
        for col in ['Alquiler Sug.', 'Gasto Cont.', 'Depósito Sug.']:
            df[col] = df[col].apply(f_m)
        st.dataframe(df, use_container_width=True, hide_index=True)
    else: st.info("Cargue datos en Maestros.")

# --- 2. NUEVO CONTRATO ---
elif menu == "📝 Nuevo Contrato":
    st.header("Generar Nuevo Contrato")
    u_df = db_query("SELECT i.id, b.nombre || ' - ' || i.tipo as ref, i.precio_alquiler, i.costo_contrato, i.deposito_base FROM inmuebles i JOIN bloques b ON i.id_bloque=b.id")
    i_df = db_query("SELECT id, nombre FROM inquilinos")
    
    if u_df is not None and i_df is not None and not u_df.empty and not i_df.empty:
        with st.form("f_con", clear_on_submit=True):
            c1, c2 = st.columns(2)
            u_id = c1.selectbox("Unidad", u_df['id'], format_func=lambda x: u_df[u_df['id']==x]['ref'].values[0])
            i_id = c2.selectbox("Inquilino", i_df['id'], format_func=lambda x: i_df[i_df['id']==x]['nombre'].values[0])
            f_ini = c1.date_input("Fecha Inicio", date.today())
            meses = c2.number_input("Meses", 1, 60, 6)
            
            row = u_df[u_df['id']==u_id].iloc[0]
            m1 = c1.text_input("Monto Alquiler", value=f_m(row['precio_alquiler']))
            m2 = c2.text_input("Gasto Contrato", value=f_m(row['costo_contrato']))
            m3 = st.text_input("Depósito", value=f_m(row['deposito_base']))
            
            if st.form_submit_button("GRABAR CONTRATO"):
                f_fin = f_ini + timedelta(days=meses*30)
                cid = db_query("INSERT INTO contratos (id_inmueble, id_inquilino, fecha_inicio, fecha_fin, monto_alquiler) VALUES (?,?,?,?,?)", 
                               (u_id, i_id, f_ini, f_fin, cl(m1)), commit=True)
                db_query("INSERT INTO deudas (id_contrato, concepto, monto_debe) VALUES (?, 'Contrato', ?)", (cid, cl(m2)), commit=True)
                db_query("INSERT INTO deudas (id_contrato, concepto, monto_debe) VALUES (?, 'Depósito', ?)", (cid, cl(m3)), commit=True)
                db_query("INSERT INTO deudas (id_contrato, concepto, monto_debe) VALUES (?, 'Mes 1', ?)", (cid, cl(m1)), commit=True)
                st.success(f"✅ Contrato {cid} creado exitosamente.")
                st.code(f"COMPROBANTE ALTA NL\nID: {cid}\nInquilino: {i_id}\nUnidad: {u_id}\nAlquiler: $ {m1}\nVence: {f_fin}")
    else: st.warning("Cargue datos previos en Maestros.")

# --- 3. COBRANZAS ---
elif menu == "💰 Cobranzas":
    st.header("Cobros Pendientes")
    deu = db_query("""
        SELECT d.id, inq.nombre, i.tipo, d.concepto, d.monto_debe 
        FROM deudas d JOIN contratos c ON d.id_contrato=c.id 
        JOIN inmuebles i ON c.id_inmueble=i.id JOIN inquilinos inq ON c.id_inquilino=inq.id 
        WHERE d.pagado=0
    """)
    if deu is not None and not deu.empty:
        for _, r in deu.iterrows():
            with st.expander(f"{r['nombre']} - {r['tipo']} (${f_m(r['monto_debe'])})"):
                if st.button(f"Confirmar Cobro: {r['concepto']}", key=f"b_{r['id']}"):
                    db_query("UPDATE deudas SET pagado=1, fecha_pago=?, monto_pago=? WHERE id=?", (date.today(), r['monto_debe'], r['id']), commit=True)
                    st.rerun()
    else: st.info("Sin deudas pendientes.")

# ==========================================
# 4. MOROSOS (V.2.7 - RECUPERADO Y FORMATEADO)
# ==========================================
elif menu == "🚨 Morosos":
    st.header("Reporte de Saldos Deudores")
    
    # Buscamos deudas no pagadas (pagado = 0)
    query_morosos = """
        SELECT 
            inq.nombre as Inquilino, 
            i.tipo as Unidad, 
            d.concepto as Concepto, 
            (d.monto_debe - d.monto_pago) as Saldo_Pendiente
        FROM deudas d
        JOIN contratos c ON d.id_contrato = c.id
        JOIN inmuebles i ON c.id_inmueble = i.id
        JOIN inquilinos inq ON c.id_inquilino = inq.id
        WHERE d.pagado = 0 AND (d.monto_debe - d.monto_pago) > 0
    """
    
    df_morosos = db_query(query_morosos)
    
    if df_morosos is not None and not df_morosos.empty:
        # Total general de morosidad para la métrica
        total_mora = df_morosos['Saldo_Pendiente'].sum()
        st.metric("Total Deuda Pendiente", f"$ {f_m(total_mora)}")
        
        # Formateamos la columna de Saldo con puntos
        df_display_mora = df_morosos.copy()
        df_display_mora['Saldo_Pendiente'] = df_display_mora['Saldo_Pendiente'].apply(f_m)
        
        # Mostramos la tabla profesional
        st.table(df_display_mora)
        
        # Opción de descarga rápida
        csv_mora = df_morosos.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Exportar Lista de Morosos (CSV)", csv_mora, "Morosos_NL.csv", "text/csv")
    else:
        st.success("✅ ¡Excelente! No se registran saldos pendientes en el sistema.")    

# --- 5. CAJA Y REPORTES ---
elif menu == "📊 Caja y Reportes":
    st.header("Reporte de Caja")
    df_c = db_query("""
        SELECT d.fecha_pago, inq.nombre as Inquilino, d.concepto, d.monto_pago 
        FROM deudas d JOIN contratos c ON d.id_contrato=c.id
        JOIN inquilinos inq ON c.id_inquilino=inq.id WHERE d.pagado=1
    """)
    if df_c is not None and not df_c.empty:
        df_c['fecha_pago'] = pd.to_datetime(df_c['fecha_pago'])
        c1, c2 = st.columns(2)
        m = c1.selectbox("Mes", range(1,13), index=date.today().month-1)
        a = c2.selectbox("Año", [2025, 2026], index=1)
        
        filtro = df_c[(df_c['fecha_pago'].dt.month == m) & (df_c['fecha_pago'].dt.year == a)].copy()
        st.metric("Recaudación del Período", f"$ {f_m(filtro['monto_pago'].sum())}")
        filtro['monto_pago'] = filtro['monto_pago'].apply(f_m)
        st.dataframe(filtro, use_container_width=True, hide_index=True)
    else: st.info("No hay pagos registrados.")

# ==========================================
# 6. MAESTROS (V.2.6 - ORDENADO Y EDITABLE)
# ==========================================
elif menu == "⚙️ Maestros":
    st.header("Panel de Administración de Maestros")
    
    # 1. ORDEN SOLICITADO: Bloques -> Unidades -> Inquilinos -> Contratos
    t1, t2, t3, t4 = st.tabs(["🏢 Bloques", "🏠 Unidades", "👤 Inquilinos", "📋 Contratos Vivos"])
    
    # --- PESTAÑA 1: BLOQUES ---
    with t1:
        st.subheader("Gestión de Bloques / Complejos")
        with st.form("f_bloque", clear_on_submit=True):
            nb = st.text_input("Nombre del Nuevo Bloque")
            if st.form_submit_button("Guardar Bloque"):
                db_query("INSERT INTO bloques (nombre) VALUES (?)", (nb,), commit=True)
                st.rerun()
        
        df_b = db_query("SELECT id, nombre FROM bloques")
        st.dataframe(df_b, use_container_width=True, hide_index=True)
        
        st.write("---")
        st.subheader("Eliminar Bloque")
        if not df_b.empty:
            sel_b_del = st.selectbox("Seleccione Bloque para eliminar", df_b['nombre'].tolist(), key="del_b")
            if st.button("🗑️ Eliminar Bloque"):
                db_query("DELETE FROM bloques WHERE nombre=?", (sel_b_del,), commit=True)
                st.rerun()

    # --- PESTAÑA 2: UNIDADES (EDICIÓN COMPLETA POR DESCRIPCIÓN) ---
    with t2:
        st.subheader("Gestión de Unidades")
        bls_u = db_query("SELECT * FROM bloques")
        
        if not bls_u.empty:
            # ALTA
            with st.expander("➕ Cargar Nueva Unidad"):
                with st.form("f_u_alta", clear_on_submit=True):
                    bid = st.selectbox("Bloque", bls_u['id'].tolist(), format_func=lambda x: bls_u[bls_u['id']==x]['nombre'].values[0])
                    ut = st.text_input("Descripción de la Unidad (Ej: Local 1)")
                    p1 = st.text_input("Alquiler Sugerido")
                    p2 = st.text_input("Gasto Contrato Sugerido")
                    p3 = st.text_input("Depósito Sugerido")
                    if st.form_submit_button("Crear Unidad"):
                        db_query("INSERT INTO inmuebles (id_bloque, tipo, precio_alquiler, costo_contrato, deposito_base) VALUES (?,?,?,?,?)", 
                                 (bid, ut, cl(p1), cl(p2), cl(p3)), commit=True); st.rerun()

            st.write("---")
            # EDICIÓN POR DESCRIPCIÓN
            st.subheader("📝 Editar Unidad Existente")
            df_u_edit = db_query("SELECT id, tipo FROM inmuebles")
            if not df_u_edit.empty:
                sel_u_edit = st.selectbox("Seleccione la Unidad a modificar", df_u_edit['tipo'].tolist())
                u_actual = db_query("SELECT * FROM inmuebles WHERE tipo=?", (sel_u_edit,)).iloc[0]
                
                with st.form("f_u_edit"):
                    new_desc = st.text_input("Nueva Descripción", value=u_actual['tipo'])
                    new_alq = st.text_input("Alquiler", value=f_m(u_actual['precio_alquiler']))
                    new_con = st.text_input("Contrato", value=f_m(u_actual['costo_contrato']))
                    new_dep = st.text_input("Depósito", value=f_m(u_actual['deposito_base']))
                    
                    c_ed1, c_ed2 = st.columns(2)
                    if c_ed1.form_submit_button("💾 Guardar Cambios"):
                        db_query("""UPDATE inmuebles SET tipo=?, precio_alquiler=?, costo_contrato=?, deposito_base=? 
                                    WHERE id=?""", (new_desc, cl(new_alq), cl(new_con), cl(new_dep), u_actual['id']), commit=True)
                        st.success("Unidad actualizada"); st.rerun()
                    
                    if c_ed2.form_submit_button("🗑️ ELIMINAR UNIDAD"):
                        db_query("DELETE FROM inmuebles WHERE id=?", (u_actual['id'],), commit=True)
                        st.rerun()

    # --- PESTAÑA 3: INQUILINOS (CAMPOS EXTENDIDOS) ---
    with t3:
        st.subheader("Ficha de Inquilinos")
        with st.form("f_inq_alta", clear_on_submit=True):
            c1, c2 = st.columns(2)
            inq_n = c1.text_input("Nombre Completo"); inq_d = c1.text_input("DNI/CUIT"); inq_c = c1.text_input("Celular")
            inq_p = c2.text_input("Procedencia"); inq_g = c2.text_input("Grupo"); inq_e = c2.text_input("Emergencia")
            if st.form_submit_button("Registrar Inquilino"):
                db_query("INSERT INTO inquilinos (nombre, dni, celular, procedencia, grupo, emergencia) VALUES (?,?,?,?,?,?)", 
                         (inq_n, inq_d, inq_c, inq_p, inq_g, inq_e), commit=True); st.rerun()
        
        st.write("---")
        df_inq_list = db_query("SELECT id, nombre, dni, celular, grupo FROM inquilinos")
        st.dataframe(df_inq_list, use_container_width=True, hide_index=True)
        
        if not df_inq_list.empty:
            sel_inq_del = st.selectbox("Seleccione Inquilino para ELIMINAR", df_inq_list['nombre'].tolist())
            if st.button("🗑️ Borrar Inquilino"):
                db_query("DELETE FROM inquilinos WHERE nombre=?", (sel_inq_del,), commit=True); st.rerun()

    # --- PESTAÑA 4: CONTRATOS VIVOS ---
    with t4:
        st.subheader("Auditoría de Contratos Activos")
        df_cv = db_query("""
            SELECT c.id, inq.nombre as Inquilino, i.tipo as Unidad, 
                   c.fecha_inicio as [F. Inicio], c.fecha_fin as [F. Vencimiento], 
                   c.monto_alquiler as Monto
            FROM contratos c 
            JOIN inquilinos inq ON c.id_inquilino = inq.id 
            JOIN inmuebles i ON c.id_inmueble = i.id
            WHERE c.activo = 1
        """)
        
        if not df_cv.empty:
            # Formato de miles para la tabla
            df_cv['Monto'] = df_cv['Monto'].apply(f_m)
            st.dataframe(df_cv, use_container_width=True, hide_index=True)
            
            st.write("---")
            sel_c_del = st.selectbox("Seleccione Contrato para DAR DE BAJA (por Inquilino - Unidad)", 
                                    df_cv.apply(lambda r: f"{r['id']} - {r['Inquilino']} ({r['Unidad']})", axis=1).tolist())
            c_id_del = sel_c_del.split(" - ")[0]
            
            if st.button("🚨 ANULAR CONTRATO SELECCIONADO"):
                db_query("DELETE FROM contratos WHERE id=?", (c_id_del,), commit=True)
                st.warning(f"Contrato {c_id_del} y sus deudas han sido eliminados."); st.rerun()
        else:
            st.info("No existen contratos activos en la base de datos.")
