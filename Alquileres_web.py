import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, date, timedelta
import os
import io

# ==========================================
# 1. IDENTIDAD Y CONFIGURACIÓN (V.2.3)
# ==========================================
st.set_page_config(page_title="NL PROPIEDADES - V.2.3", layout="wide")
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
    with sqlite3.connect('datos_alquileres.db', check_same_thread=False) as conn:
        if commit:
            cur = conn.cursor()
            cur.execute(sql, params)
            conn.commit()
            return cur.lastrowid
        return pd.read_sql_query(sql, conn, params=params)

# Inicialización con nuevos campos
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
    
    st.info("🚀 VERSIÓN: V.2.3 - FULL")
    menu = st.radio("MENÚ:", ["🏠 Inventario", "📝 Nuevo Contrato", "💰 Cobranzas", "📊 Caja y Filtros", "📊 Caja y Reportes", "⚙️ Maestros"])
    
    if st.button("🚨 RESET BASE"):
        if os.path.exists('datos_alquileres.db'): os.remove('datos_alquileres.db')
        st.rerun()

# ==========================================
# 4. SECCIONES
# ==========================================

# --- 1. INVENTARIO ---
if menu == "🏠 Inventario":
    st.header("Inventario de Unidades")
    df = db_query("""
        SELECT b.nombre as Bloque, i.tipo as Unidad, i.precio_alquiler, i.costo_contrato, i.deposito_base,
        CASE WHEN c.activo = 1 THEN '🔴 OCUPADO' ELSE '🟢 LIBRE' END as Estado,
        CASE WHEN c.activo = 1 THEN c.fecha_fin ELSE 'HOY' END as [Disponible]
        FROM inmuebles i JOIN bloques b ON i.id_bloque = b.id
        LEFT JOIN contratos c ON i.id = c.id_inmueble AND c.activo = 1
    """)
    if not df.empty:
        # Formatear importes en el DataFrame
        for col in ['precio_alquiler', 'costo_contrato', 'deposito_base']:
            df[col] = df[col].apply(f_m)
        st.dataframe(df, use_container_width=True, hide_index=True)

# --- 2. NUEVO CONTRATO ---
elif menu == "📝 Nuevo Contrato":
    st.header("Nuevo Contrato")
    u_df = db_query("SELECT i.id, b.nombre || ' - ' || i.tipo as ref, i.precio_alquiler, i.costo_contrato, i.deposito_base FROM inmuebles i JOIN bloques b ON i.id_bloque=b.id")
    i_df = db_query("SELECT id, nombre FROM inquilinos")
    
    if not u_df.empty and not i_df.empty:
        with st.form("f_con", clear_on_submit=True):
            c1, c2 = st.columns(2)
            u_id = c1.selectbox("Unidad", u_df['id'], format_func=lambda x: u_df[u_df['id']==x]['ref'].values[0])
            i_id = c2.selectbox("Inquilino", i_df['id'], format_func=lambda x: i_df[i_df['id']==x]['nombre'].values[0])
            f_ini = c1.date_input("Inicio", date.today())
            meses = c2.number_input("Meses", 1, 60, 6)
            
            row = u_df[u_df['id']==u_id].iloc[0]
            m1 = c1.text_input("Alquiler", value=f_m(row['precio_alquiler']))
            m2 = c2.text_input("Gasto Contrato", value=f_m(row['costo_contrato']))
            m3 = st.text_input("Depósito", value=f_m(row['deposito_base']))
            
            if st.form_submit_button("GRABAR Y GENERAR DOCUMENTO"):
                f_fin = f_ini + timedelta(days=meses*30)
                cid = db_query("INSERT INTO contratos (id_inmueble, id_inquilino, fecha_inicio, fecha_fin, monto_alquiler) VALUES (?,?,?,?,?)", (u_id, i_id, f_ini, f_fin, cl(m1)), commit=True)
                db_query("INSERT INTO deudas (id_contracto, concepto, monto_debe) VALUES (?, 'Contrato', ?)", (cid, cl(m2)), commit=True)
                db_query("INSERT INTO deudas (id_contrato, concepto, monto_debe) VALUES (?, 'Depósito', ?)", (cid, cl(m3)), commit=True)
                db_query("INSERT INTO deudas (id_contrato, concepto, monto_debe) VALUES (?, 'Mes 1', ?)", (cid, cl(m1)), commit=True)
                
                st.success("✅ Contrato Grabado")
                # Documento de Resumen
                st.subheader("📄 Resumen de Contrato (Para Copiar)")
                resumen = f"""
                PROPIEDADES NL - COMPROBANTE DE ALTA
                ------------------------------------
                ID Contrato: {cid} | Fecha: {date.today()}
                Inquilino ID: {i_id}
                Unidad: {u_id}
                Periodo: {f_ini} hasta {f_fin}
                Alquiler Pactado: $ {m1}
                ------------------------------------
                """
                st.code(resumen)

# --- 3. COBRANZAS ---
elif menu == "💰 Cobranzas":
    st.header("Cobranzas")
    deu = db_query("SELECT d.id, inq.nombre, i.tipo, d.concepto, d.monto_debe FROM deudas d JOIN contratos c ON d.id_contrato=c.id JOIN inmuebles i ON c.id_inmueble=i.id JOIN inquilinos inq ON c.id_inquilino=inq.id WHERE d.pagado=0")
    for _, r in deu.iterrows():
        with st.expander(f"{r['nombre']} - {r['tipo']} (${f_m(r['monto_debe'])})"):
            if st.button(f"Cobrar {r['concepto']}", key=f"b_{r['id']}"):
                db_query("UPDATE deudas SET pagado=1, fecha_pago=?, monto_pago=? WHERE id=?", (date.today(), r['monto_debe'], r['id']), commit=True)
                st.rerun()

# --- 4. CAJA Y FILTROS ---
elif menu == "📊 Caja y Filtros":
    st.header("Reporte de Caja")
    df_c = db_query("SELECT fecha_pago, concepto, monto_pago FROM deudas WHERE pagado=1")
    if not df_c.empty:
        df_c['fecha_pago'] = pd.to_datetime(df_c['fecha_pago'])
        c1, c2 = st.columns(2)
        mes = c1.selectbox("Mes", range(1,13), index=date.today().month-1)
        anio = c2.selectbox("Año", [2025, 2026], index=1)
        
        filtro = df_c[(df_c['fecha_pago'].dt.month == mes) & (df_c['fecha_pago'].dt.year == anio)]
        st.metric("Total del Periodo", f"$ {f_m(filtro['monto_pago'].sum())}")
        st.dataframe(filtro, use_container_width=True)

# ==========================================
# 5. CAJA Y REPORTES (CON FILTROS Y EXCEL)
# ==========================================
elif menu == "📊 Caja y Reportes":
    st.header("Control de Caja y Exportación")
    
    # Traemos todos los pagos realizados
    df_pagos = db_query("""
        SELECT d.fecha_pago as Fecha, inq.nombre as Inquilino, i.tipo as Unidad, 
               d.concepto as Detalle, d.monto_pago as Importe
        FROM deudas d
        JOIN contratos c ON d.id_contrato = c.id
        JOIN inmuebles i ON c.id_inmueble = i.id
        JOIN inquilinos inq ON c.id_inquilino = inq.id
        WHERE d.pagado = 1
    """)

    if df_pagos is not None and not df_pagos.empty:
        # Convertimos la fecha para poder filtrar
        df_pagos['Fecha'] = pd.to_datetime(df_pagos['Fecha'])
        
        # --- FILTROS DE BÚSQUEDA ---
        st.subheader("Filtros de Período")
        c1, c2, c3 = st.columns([2, 2, 2])
        
        mes_sel = c1.selectbox("Mes", 
                               range(1, 13), 
                               index=datetime.now().month - 1,
                               format_func=lambda x: ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", 
                                                      "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"][x-1])
        
        anio_sel = c2.selectbox("Año", [2025, 2026, 2027], index=1) # 2026 por defecto
        
        # Aplicar Filtro
        df_filtrado = df_pagos[(df_pagos['Fecha'].dt.month == mes_sel) & (df_pagos['Fecha'].dt.year == anio_sel)].copy()
        
        # --- MÉTRICAS ---
        total_periodo = df_filtrado['Importe'].sum()
        st.metric(label=f"Total Recaudado en {mes_sel}/{anio_sel}", value=f"$ {f_m(total_periodo)}")
        
        # --- TABLA DE DATOS ---
        # Formateamos la fecha para mostrar solo día/mes/año
        df_display = df_filtrado.copy()
        df_display['Fecha'] = df_display['Fecha'].dt.strftime('%d/%m/%Y')
        df_display['Importe'] = df_display['Importe'].apply(f_m)
        
        st.dataframe(df_display, use_container_width=True, hide_index=True)

        # --- EXPORTACIÓN ---
        st.write("---")
        st.subheader("Descargar Reporte")
        col_ex1, col_ex2 = st.columns(2)
        
        # Opción 1: Excel (Requiere xlsxwriter en requirements.txt)
        try:
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                df_filtrado.to_excel(writer, index=False, sheet_name='Reporte_Caja')
            
            col_ex1.download_button(
                label="📥 Descargar Excel (.xlsx)",
                data=buffer.getvalue(),
                file_name=f"Caja_NL_{mes_sel}_{anio_sel}.xlsx",
                mime="application/vnd.ms-excel"
            )
        except Exception as e:
            col_ex1.warning("Error al generar Excel. Use la opción CSV.")

        # Opción 2: CSV (Plan B infalible)
        csv = df_filtrado.to_csv(index=False).encode('utf-8')
        col_ex2.download_button(
            label="📄 Descargar CSV (Texto plano)",
            data=csv,
            file_name=f"Caja_NL_{mes_sel}_{anio_sel}.csv",
            mime="text/csv"
        )
    else:
        st.info("Aún no se han registrado cobros en el sistema.")

# ==========================================
# 6. MAESTROS (ABM COMPLETO + SECCIÓN CONTRATOS)
# ==========================================
elif menu == "⚙️ Maestros":
    st.header("Configuración de Maestros y Gestión de Datos")
    t1, t2, t3, t4 = st.tabs(["👤 Inquilinos", "🏠 Unidades", "🏢 Bloques", "📋 Contratos Activos"])
    
    with t1:
        st.subheader("Registro de Inquilinos")
        with st.form("fi", clear_on_submit=True):
            col1, col2 = st.columns(2)
            n = col1.text_input("Nombre y Apellido")
            d = col1.text_input("DNI / CUIT")
            cel = col1.text_input("Teléfono / WhatsApp")
            pro = col2.text_input("Procedencia (Ciudad/Barrio)")
            gru = col2.text_input("Grupo / Referencia")
            eme = col2.text_input("Contacto Emergencia (Nombre y Tel)")
            if st.form_submit_button("Guardar Inquilino"):
                db_query("INSERT INTO inquilinos (nombre, dni, celular, emergencia, procedencia, grupo) VALUES (?,?,?,?,?,?)", 
                         (n, d, cel, eme, pro, gru), commit=True)
                st.success(f"Inquilino {n} guardado."); st.rerun()
        
        df_inq = db_query("SELECT id, nombre, dni, celular, grupo FROM inquilinos")
        st.dataframe(df_inq, use_container_width=True, hide_index=True)
        
        idx_inq = st.number_input("ID Inquilino a eliminar", step=1, value=0, key="del_inq_id")
        if st.button("🗑️ Eliminar Inquilino"):
            db_query(f"DELETE FROM inquilinos WHERE id={idx_inq}", commit=True)
            st.rerun()

    with t2:
        st.subheader("Gestión de Unidades")
        bls = db_query("SELECT * FROM bloques")
        if not bls.empty:
            with st.form("fu", clear_on_submit=True):
                bid = st.selectbox("Bloque", bls['id'].tolist(), format_func=lambda x: bls[bls['id']==x]['nombre'].values[0])
                ut = st.text_input("Nombre de la Unidad (Ej: Depto 2A)")
                p1 = st.text_input("Precio Alquiler Sugerido")
                p2 = st.text_input("Gasto Contrato Sugerido")
                p3 = st.text_input("Depósito Sugerido")
                if st.form_submit_button("Crear Unidad"):
                    db_query("INSERT INTO inmuebles (id_bloque, tipo, precio_alquiler, costo_contrato, deposito_base) VALUES (?,?,?,?,?)", 
                             (bid, ut, cl(p1), cl(p2), cl(p3)), commit=True)
                    st.success("Unidad creada."); st.rerun()
        
        df_uni = db_query("SELECT i.id, b.nombre as Bloque, i.tipo as Unidad, i.precio_alquiler FROM inmuebles i JOIN bloques b ON i.id_bloque=b.id")
        st.dataframe(df_uni, use_container_width=True, hide_index=True)
        
        st.write("---")
        st.subheader("Edición / Eliminación")
        col_ed1, col_ed2 = st.columns(2)
        id_u = col_ed1.number_input("ID Unidad", step=1, value=0, key="edit_u_id")
        if id_u > 0:
            u_data = db_query(f"SELECT * FROM inmuebles WHERE id={id_u}")
            if not u_data.empty:
                new_val = col_ed2.text_input("Nuevo Alquiler Sugerido", value=f_m(u_data['precio_alquiler'].iloc[0]))
                if st.button("💾 Actualizar Precio"):
                    db_query(f"UPDATE inmuebles SET precio_alquiler={cl(new_val)} WHERE id={id_u}", commit=True)
                    st.success("Precio actualizado."); st.rerun()
        
        if st.button("🗑️ Eliminar Unidad Seleccionada"):
            db_query(f"DELETE FROM inmuebles WHERE id={id_u}", commit=True); st.rerun()

    with t3:
        st.subheader("Bloques / Complejos")
        nb = st.text_input("Nombre del Nuevo Bloque")
        if st.button("Añadir Bloque"):
            db_query("INSERT INTO bloques (nombre) VALUES (?)", (nb,), commit=True); st.rerun()
        st.table(db_query("SELECT * FROM bloques"))

    with t4:
        st.subheader("📋 Auditoría de Contratos Activos")
        # Esta es la parte que habíamos perdido
        df_cont_act = db_query("""
            SELECT c.id as ID, inq.nombre as Inquilino, b.nombre as Bloque, i.tipo as Unidad, 
                   c.fecha_inicio as Inicio, c.fecha_fin as Vencimiento, c.monto_alquiler as Monto
            FROM contratos c 
            JOIN inquilinos inq ON c.id_inquilino = inq.id 
            JOIN inmuebles i ON c.id_inmueble = i.id
            JOIN bloques b ON i.id_bloque = b.id
            WHERE c.activo = 1
        """)
        
        if not df_cont_act.empty:
            # Formateamos el monto para la vista
            df_cont_act['Monto'] = df_cont_act['Monto'].apply(f_m)
            st.dataframe(df_cont_act, use_container_width=True, hide_index=True)
            
            st.write("---")
            id_c_del = st.number_input("ID de Contrato para DAR DE BAJA / ELIMINAR", step=1, value=0)
            if st.button("🚨 Eliminar Contrato y sus Deudas"):
                # Al eliminar el contrato, por el ON DELETE CASCADE del motor, se borran sus deudas
                db_query(f"DELETE FROM contratos WHERE id={id_c_del}", commit=True)
                st.warning(f"Contrato {id_c_del} eliminado del sistema."); st.rerun()
        else:
            st.info("No hay contratos vigentes en este momento.")
