import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, date, timedelta
import os

# ==========================================
# 1. CONFIGURACIÓN Y MOTOR DE BASE DE DATOS
# ==========================================
st.set_page_config(page_title="Inmobiliaria Pro", layout="wide")

def conectar():
    return sqlite3.connect('datos_alquileres.db', check_same_thread=False, timeout=20)

def fmt_moneda(valor):
    try: 
        return f"$ {int(float(valor or 0)):,}".replace(",", ".")
    except: 
        return "$ 0"

def limpiar_monto(texto):
    if not texto: return 0
    try: 
        # Convertimos a entero para evitar decimales
        return int(float(str(texto).replace('$', '').replace('.', '').replace(',', '').strip()))
    except: 
        return 0

def inicializar_db():
    conn = conectar()
    c = conn.cursor()
    # Script de creación con TODOS los campos solicitados
    c.executescript('''
        CREATE TABLE IF NOT EXISTS bloques (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            nombre TEXT UNIQUE
        );
        CREATE TABLE IF NOT EXISTS inmuebles (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            id_bloque INTEGER, 
            tipo TEXT, 
            precio_alquiler INTEGER, 
            costo_contrato INTEGER, 
            deposito_base INTEGER, 
            UNIQUE(id_bloque, tipo)
        );
        CREATE TABLE IF NOT EXISTS inquilinos (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            nombre TEXT, 
            celular TEXT, 
            dni TEXT, 
            direccion TEXT,
            emergencia_contacto TEXT, 
            procedencia TEXT, 
            grupo TEXT
        );
        CREATE TABLE IF NOT EXISTS contratos (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            id_inmueble INTEGER, 
            id_inquilino INTEGER, 
            fecha_inicio DATE, 
            fecha_fin DATE, 
            meses INTEGER, 
            activo INTEGER DEFAULT 1, 
            monto_alquiler INTEGER, 
            monto_contrato INTEGER, 
            monto_deposito INTEGER
        );
        CREATE TABLE IF NOT EXISTS deudas (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            id_contrato INTEGER, 
            concepto TEXT, 
            mes_anio TEXT, 
            monto_debe INTEGER, 
            monto_pago INTEGER DEFAULT 0, 
            pagado INTEGER DEFAULT 0, 
            fecha_cobro DATE
        );
    ''')
    conn.commit()
    conn.close()

inicializar_db()

# ==========================================
# MENÚ LATERAL
# ==========================================
with st.sidebar:
    st.title("🏢 Menú Principal")
    menu = st.radio("Seleccione una sección:", 
                    ["🏠 1. Inventario", "📝 2. Nuevo Contrato", "💰 3. Cobranzas", 
                     "🚨 4. Morosos", "📊 5. Caja", "⚙️ 6. Maestros"])
    st.divider()
    if st.button("🚨 REINICIAR TODA LA BASE"):
        if os.path.exists('datos_alquileres.db'): os.remove('datos_alquileres.db')
        inicializar_db()
        st.rerun()

# ==========================================
# 🏠 SECCIÓN 1: INVENTARIO
# ==========================================
if menu == "🏠 1. Inventario":
    st.header("Estado de Unidades y Disponibilidad")
    conn = conectar()
    df = pd.read_sql_query("""
        SELECT i.id, b.nombre as Bloque, i.tipo as Unidad, 
               i.precio_alquiler as [Alquiler ($)], 
               i.costo_contrato as [Contrato ($)], 
               i.deposito_base as [Depósito ($)],
               c.fecha_fin, c.activo FROM inmuebles i
        JOIN bloques b ON i.id_bloque = b.id
        LEFT JOIN contratos c ON i.id = c.id_inmueble AND c.activo = 1
    """, conn)
    conn.close()

    if not df.empty:
        def calc_estado(row):
            if pd.isna(row['activo']) or row['activo'] == 0: return "🟢 LIBRE", "HOY"
            return "🔴 OCUPADO", row['fecha_fin']

        df[['Estado', 'Disponible']] = df.apply(lambda x: pd.Series(calc_estado(x)), axis=1)
        for col in ['Alquiler ($)', 'Contrato ($)', 'Depósito ($)']:
            df[col] = df[col].apply(fmt_moneda)

        st.dataframe(df[["Bloque", "Unidad", "Estado", "Disponible", "Alquiler ($)", "Contrato ($)", "Depósito ($)"]], 
                     use_container_width=True, hide_index=True)
    else: st.info("No hay unidades cargadas en Maestros.")

# ==========================================
# 📝 SECCIÓN 2: NUEVO CONTRATO
# ==========================================
elif menu == "📝 2. Nuevo Contrato":
    st.header("Alta de Alquiler")
    conn = conectar()
    inm = pd.read_sql_query("SELECT i.id, b.nombre || ' - ' || i.tipo as ref, i.precio_alquiler, i.costo_contrato, i.deposito_base FROM inmuebles i JOIN bloques b ON i.id_bloque=b.id", conn)
    inq = pd.read_sql_query("SELECT * FROM inquilinos", conn)
    
    if not inm.empty and not inq.empty:
        with st.form("nuevo_con"):
            c1, c2 = st.columns(2)
            sel_inm = c1.selectbox("Unidad", inm['id'].tolist(), format_func=lambda x: inm[inm['id']==x]['ref'].values[0])
            sel_inq = c2.selectbox("Inquilino", inq['id'].tolist(), format_func=lambda x: inq[inq['id']==x]['nombre'].values[0])
            f_ini = c1.date_input("Fecha Inicio", date.today())
            meses = c2.number_input("Duración (Meses)", min_value=1, value=6)
            
            datos_u = inm[inm['id']==sel_inm].iloc[0]
            m_alq = c1.text_input("Alquiler Pactado", value=str(int(datos_u['precio_alquiler'])))
            m_con = c2.text_input("Costo Contrato Pactado", value=str(int(datos_u['costo_contrato'])))
            m_dep = c1.text_input("Depósito Pactado", value=str(int(datos_u['deposito_base'])))
            
            if st.form_submit_button("Confirmar Contrato"):
                f_fin = f_ini + timedelta(days=meses*30)
                conn.execute("""INSERT INTO contratos 
                    (id_inmueble, id_inquilino, fecha_inicio, fecha_fin, meses, activo, monto_alquiler, monto_contrato, monto_deposito) 
                    VALUES (?,?,?,?,?,1,?,?,?)""",
                    (sel_inm, sel_inq, f_ini, f_fin, meses, limpiar_monto(m_alq), limpiar_monto(m_con), limpiar_monto(m_dep)))
                conn.commit(); st.success("Contrato guardado correctamente"); st.rerun()
    else: st.warning("Faltan datos maestros (Inquilinos/Unidades).")
    conn.close()

# ==========================================
# 💰 SECCIÓN 3: COBRANZAS
# ==========================================
elif menu == "💰 3. Cobranzas":
    st.header("Gestión de Cobros")
    conn = conectar()
    deudas = pd.read_sql_query("""
        SELECT d.id, inq.nombre, i.tipo, d.concepto, d.mes_anio, d.monto_debe, d.monto_pago 
        FROM deudas d JOIN contratos c ON d.id_contrato=c.id
        JOIN inmuebles i ON c.id_inmueble=i.id JOIN inquilinos inq ON c.id_inquilino=inq.id
        WHERE d.pagado = 0
    """, conn)
    
    for _, r in deudas.iterrows():
        with st.expander(f"📌 {r['nombre']} - {r['tipo']} ({r['mes_anio']})"):
            saldo = r['monto_debe'] - r['monto_pago']
            st.write(f"Deuda Total: {fmt_moneda(r['monto_debe'])} | Saldo Pendiente: {fmt_moneda(saldo)}")
            pago = st.text_input(f"Cobrar", value=str(int(saldo)), key=f"p_{r['id']}")
            col1, col2 = st.columns(2)
            if col1.button("Confirmar Pago", key=f"btn_{r['id']}"):
                nuevo_p = r['monto_pago'] + limpiar_monto(pago)
                pagado = 1 if nuevo_p >= r['monto_debe'] else 0
                conn.execute("UPDATE deudas SET monto_pago=?, pagado=?, fecha_cobro=? WHERE id=?", (nuevo_p, pagado, date.today(), r['id']))
                conn.commit(); st.rerun()
            if col2.button("🗑️ Eliminar Cuota", key=f"del_{r['id']}"):
                conn.execute("DELETE FROM deudas WHERE id=?", (r['id'],))
                conn.commit(); st.rerun()
    conn.close()

# ==========================================
# 🚨 SECCIÓN 4: MOROSOS
# ==========================================
elif menu == "🚨 4. Morosos":
    st.header("Reporte de Morosidad")
    conn = conectar()
    df_m = pd.read_sql_query("""
        SELECT inq.nombre as Inquilino, i.tipo as Unidad, d.concepto as Concepto, d.mes_anio as Periodo,
               (d.monto_debe - d.monto_pago) as Saldo, inq.celular as WhatsApp
        FROM deudas d JOIN contratos c ON d.id_contrato = c.id
        JOIN inmuebles i ON c.id_inmueble = i.id JOIN inquilinos inq ON c.id_inquilino = inq.id
        WHERE d.pagado = 0
    """, conn)
    conn.close()
    if not df_m.empty:
        df_m['Saldo'] = df_m['Saldo'].apply(fmt_moneda)
        st.dataframe(df_m, use_container_width=True, hide_index=True)
    else: st.success("No hay deudas pendientes.")

# ==========================================
# 📊 SECCIÓN 5: CAJA
# ==========================================
elif menu == "📊 5. Caja":
    st.header("Resumen de Ingresos")
    c1, c2 = st.columns(2)
    f_d = c1.date_input("Desde", date.today() - timedelta(days=30))
    f_h = c2.date_input("Hasta", date.today())
    conn = conectar()
    df_caja = pd.read_sql_query("SELECT fecha_cobro as Fecha, concepto as Detalle, monto_pago as Importe FROM deudas WHERE pagado = 1 AND fecha_cobro BETWEEN ? AND ?", conn, params=(f_d, f_h))
    if not df_caja.empty:
        st.metric("Total Recaudado", fmt_moneda(df_caja['Importe'].sum()))
        df_caja['Importe'] = df_caja['Importe'].apply(fmt_moneda)
        st.table(df_caja)
    conn.close()

# ==========================================
# ⚙️ SECCIÓN 6: MAESTROS (GESTIÓN COMPLETA)
# ==========================================
elif menu == "⚙️ 6. Maestros":
    st.header("Administración de Datos Maestros")
    t1, t2, t3, t4, t5 = st.tabs(["👤 Inquilinos", "🏢 Bloques", "🏠 Unidades", "📝 Contratos", "🚀 Procesos"])
    
    with t1: # INQUILINOS MEJORADOS
        con = conectar()
        inqs_df = pd.read_sql_query("SELECT * FROM inquilinos", con)
        col_i1, col_i2 = st.columns(2)
        
        with col_i1:
            st.write("#### ➕ Cargar / ✏️ Editar Inquilino")
            modo = st.radio("Acción:", ["Nuevo", "Editar"], horizontal=True)
            v_id, v_nom, v_cel, v_dni, v_dir, v_eme, v_pro, v_gru = None, "", "", "", "", "", "", ""
            if modo == "Editar" and not inqs_df.empty:
                sel_i = st.selectbox("Elegir:", inqs_df['id'].tolist(), format_func=lambda x: inqs_df[inqs_df['id']==x]['nombre'].values[0])
                f = inqs_df[inqs_df['id']==sel_i].iloc[0]
                v_id, v_nom, v_cel, v_dni, v_dir, v_eme, v_pro, v_gru = f['id'], f['nombre'], f['celular'], f['dni'], f['direccion'], f['emergencia_contacto'], f['procedencia'], f['grupo']

            with st.form("f_inquilino"):
                f_nom = st.text_input("Nombre y Apellido", value=v_nom)
                f_dni = st.text_input("DNI / Documento", value=v_dni)
                f_cel = st.text_input("WhatsApp", value=v_cel)
                f_dir = st.text_input("Dirección", value=v_dir)
                st.divider()
                c_a, c_b, c_c = st.columns(3)
                f_pro = c_a.text_input("Procedencia", value=v_pro)
                f_gru = c_b.text_input("Grupo", value=v_gru)
                f_eme = c_c.text_input("Emergencia", value=v_eme)
                if st.form_submit_button("Guardar"):
                    if modo == "Nuevo":
                        con.execute("INSERT INTO inquilinos (nombre, celular, dni, direccion, emergencia_contacto, procedencia, grupo) VALUES (?,?,?,?,?,?,?)", (f_nom, f_cel, f_dni, f_dir, f_eme, f_pro, f_gru))
                    else:
                        con.execute("UPDATE inquilinos SET nombre=?, celular=?, dni=?, direccion=?, emergencia_contacto=?, procedencia=?, grupo=? WHERE id=?", (f_nom, f_cel, f_dni, f_dir, f_eme, f_pro, f_gru, v_id))
                    con.commit(); st.rerun()
        
        with col_i2:
            st.write("#### 🗑️ Eliminar Inquilino")
            if not inqs_df.empty:
                id_del = st.selectbox("Inquilino a borrar", inqs_df['id'].tolist(), format_func=lambda x: inqs_df[inqs_df['id']==x]['nombre'].values[0], key="del_inq")
                if st.button("BORRAR DEFINITIVAMENTE"):
                    con.execute("DELETE FROM inquilinos WHERE id=?", (id_del,))
                    con.commit(); st.rerun()

        st.write("### 📋 Lista y Ubicación de Inquilinos")
        df_preview = pd.read_sql_query("""
            SELECT inq.nombre as Nombre, inq.grupo as Grupo, inq.procedencia as Origen, 
                   IFNULL(b.nombre || ' - ' || i.tipo, '❌ SIN ALQUILER') as [Ubicación Actual]
            FROM inquilinos inq
            LEFT JOIN contratos c ON inq.id = c.id_inquilino AND c.activo = 1
            LEFT JOIN inmuebles i ON c.id_inmueble = i.id
            LEFT JOIN bloques b ON i.id_bloque = b.id
        """, con)
        st.dataframe(df_preview, use_container_width=True, hide_index=True)
        con.close()

    with t2: # BLOQUES
        con = conectar()
        st.write("#### 🏢 Gestión de Bloques")
        nb = st.text_input("Nombre del Bloque")
        if st.button("Guardar Bloque"):
            con.execute("INSERT INTO bloques (nombre) VALUES (?)", (nb,))
            con.commit(); st.rerun()
        bls = pd.read_sql_query("SELECT * FROM bloques", con)
        if not bls.empty:
            id_b_del = st.selectbox("Borrar Bloque", bls['id'].tolist(), format_func=lambda x: bls[bls['id']==x]['nombre'].values[0])
            if st.button("ELIMINAR BLOQUE"):
                con.execute("DELETE FROM bloques WHERE id=?", (id_b_del,))
                con.commit(); st.rerun()
        con.close()

    with t3: # UNIDADES (CARGA Y EDICIÓN)
        con = conectar()
        st.write("#### 🏠 Gestión de Unidades")
        c_u1, c_u2 = st.columns(2)
        with c_u1:
            st.write("➕ Nueva")
            bls_u = pd.read_sql_query("SELECT * FROM bloques", con)
            if not bls_u.empty:
                with st.form("f_u_new"):
                    idb = st.selectbox("Bloque", bls_u['id'].tolist(), format_func=lambda x: bls_u[bls_u['id']==x]['nombre'].values[0])
                    tp = st.text_input("Unidad")
                    pr, co, de = st.columns(3)
                    m1 = pr.text_input("Alquiler")
                    m2 = co.text_input("Contrato")
                    m3 = de.text_input("Depósito")
                    if st.form_submit_button("Guardar"):
                        con.execute("INSERT INTO inmuebles (id_bloque, tipo, precio_alquiler, costo_contrato, deposito_base) VALUES (?,?,?,?,?)", (idb, tp, limpiar_monto(m1), limpiar_monto(m2), limpiar_monto(m3)))
                        con.commit(); st.rerun()
        with c_u2:
            st.write("✏️ Editar")
            inms = pd.read_sql_query("SELECT i.id, b.nombre || ' - ' || i.tipo as ref, i.precio_alquiler, i.costo_contrato, i.deposito_base FROM inmuebles i JOIN bloques b ON i.id_bloque=b.id", con)
            if not inms.empty:
                sel_u = st.selectbox("Unidad:", inms['id'].tolist(), format_func=lambda x: inms[inms['id']==x]['ref'].values[0])
                u = inms[inms['id']==sel_u].iloc[0]
                with st.form("f_u_edit"):
                    e1, e2, e3 = st.text_input("Alquiler", value=str(int(u['precio_alquiler']))), st.text_input("Contrato", value=str(int(u['costo_contrato']))), st.text_input("Depósito", value=str(int(u['deposito_base'])))
                    if st.form_submit_button("Actualizar"):
                        con.execute("UPDATE inmuebles SET precio_alquiler=?, costo_contrato=?, deposito_base=? WHERE id=?", (limpiar_monto(e1), limpiar_monto(e2), limpiar_monto(e3), sel_u))
                        con.commit(); st.rerun()
                if st.button("🗑️ ELIMINAR UNIDAD"):
                    con.execute("DELETE FROM inmuebles WHERE id=?", (sel_u,))
                    con.commit(); st.rerun()
        con.close()

    with t4: # CONTRATOS
        con = conectar()
        st.write("#### 🗑️ Borrar Contrato")
        c_df = pd.read_sql_query("SELECT c.id, inq.nombre || ' - ' || i.tipo as ref FROM contratos c JOIN inquilinos inq ON c.id_inquilino=inq.id JOIN inmuebles i ON c.id_inmueble=i.id", con)
        if not c_df.empty:
            id_c_del = st.selectbox("Seleccionar:", c_df['id'].tolist(), format_func=lambda x: c_df[c_df['id']==x]['ref'].values[0])
            if st.button("ELIMINAR CONTRATO Y SUS DEUDAS"):
                con.execute("DELETE FROM deudas WHERE id_contrato=?", (id_c_del,))
                con.execute("DELETE FROM contratos WHERE id=?", (id_c_del,))
                con.commit(); st.rerun()
        con.close()

    with t5: # PROCESOS
        st.write("#### 🚀 Generación Mensual")
        mes_anio = st.text_input("Mes/Año (Ej: Mayo 2026)")
        if st.button("GENERAR CUOTAS"):
            con = conectar()
            activos = pd.read_sql_query("SELECT id, monto_alquiler FROM contratos WHERE activo=1", con)
            for _, c in activos.iterrows():
                con.execute("INSERT INTO deudas (id_contrato, concepto, mes_anio, monto_debe) VALUES (?, 'Alquiler', ?, ?)", (c['id'], mes_anio, c['monto_alquiler']))
            con.commit(); con.close(); st.success("¡Cuotas generadas!")
