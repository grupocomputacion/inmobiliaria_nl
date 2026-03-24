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
        return int(float(str(texto).replace('$', '').replace('.', '').replace(',', '').strip()))
    except: 
        return 0

def inicializar_db():
    conn = conectar()
    c = conn.cursor()
    c.executescript('''
        CREATE TABLE IF NOT EXISTS bloques (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT UNIQUE);
        CREATE TABLE IF NOT EXISTS inmuebles (
            id INTEGER PRIMARY KEY AUTOINCREMENT, id_bloque INTEGER, tipo TEXT, 
            precio_alquiler INTEGER, costo_contrato INTEGER, deposito_base INTEGER, UNIQUE(id_bloque, tipo)
        );
        CREATE TABLE IF NOT EXISTS inquilinos (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT, celular TEXT);
        CREATE TABLE IF NOT EXISTS contratos (
            id INTEGER PRIMARY KEY AUTOINCREMENT, id_inmueble INTEGER, id_inquilino INTEGER, 
            fecha_inicio DATE, fecha_fin DATE, meses INTEGER, activo INTEGER DEFAULT 1, 
            monto_alquiler INTEGER, monto_contrato INTEGER, monto_deposito INTEGER
        );
        CREATE TABLE IF NOT EXISTS deudas (
            id INTEGER PRIMARY KEY AUTOINCREMENT, id_contrato INTEGER, concepto TEXT, 
            mes_anio TEXT, monto_debe INTEGER, monto_pago INTEGER DEFAULT 0, pagado INTEGER DEFAULT 0, fecha_cobro DATE
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
    if st.button("🚨 BORRADO TOTAL (RESET)"):
        if os.path.exists('datos_alquileres.db'): os.remove('datos_alquileres.db')
        inicializar_db()
        st.rerun()

# ==========================================
# 🏠 SECCIÓN 1: INVENTARIO (Columnas completas)
# ==========================================
if menu == "🏠 1. Inventario":
    st.header("Estado de Unidades")
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
        
        # Aplicamos formato moneda a las columnas de dinero
        for col in ['Alquiler ($)', 'Contrato ($)', 'Depósito ($)']:
            df[col] = df[col].apply(fmt_moneda)

        st.dataframe(df[["Bloque", "Unidad", "Estado", "Disponible", "Alquiler ($)", "Contrato ($)", "Depósito ($)"]], 
                     use_container_width=True, hide_index=True)
    else: st.info("No hay unidades cargadas.")

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
            m_alq = c1.text_input("Alquiler Mensual pactado", value=str(int(datos_u['precio_alquiler'])))
            m_con = c2.text_input("Costo Contrato pactado", value=str(int(datos_u['costo_contrato'])))
            m_dep = c1.text_input("Depósito pactado", value=str(int(datos_u['deposito_base'])))
            
            if st.form_submit_button("Confirmar Contrato"):
                f_fin = f_ini + timedelta(days=meses*30)
                conn.execute("""INSERT INTO contratos 
                    (id_inmueble, id_inquilino, fecha_inicio, fecha_fin, meses, activo, monto_alquiler, monto_contrato, monto_deposito) 
                    VALUES (?,?,?,?,?,1,?,?,?)""",
                    (sel_inm, sel_inq, f_ini, f_fin, meses, limpiar_monto(m_alq), limpiar_monto(m_con), limpiar_monto(m_dep)))
                conn.commit(); st.success("Contrato creado exitosamente"); st.rerun()
    else: st.warning("Asegúrese de tener Inquilinos, Bloques y Unidades cargadas en Maestros.")
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
    
    if deudas.empty: st.info("No hay cuotas pendientes de cobro.")
    for _, r in deudas.iterrows():
        with st.expander(f"📌 {r['nombre']} - {r['tipo']} ({r['mes_anio']})"):
            saldo = r['monto_debe'] - r['monto_pago']
            st.write(f"Deuda: {fmt_moneda(r['monto_debe'])} | Pagado: {fmt_moneda(r['monto_pago'])}")
            pago = st.text_input(f"Monto a recibir", value=str(int(saldo)), key=f"p_{r['id']}")
            c_p1, c_p2 = st.columns(2)
            if c_p1.button("Confirmar Pago", key=f"btn_{r['id']}"):
                nuevo_p = r['monto_pago'] + limpiar_monto(pago)
                pagado = 1 if nuevo_p >= r['monto_debe'] else 0
                conn.execute("UPDATE deudas SET monto_pago=?, pagado=?, fecha_cobro=? WHERE id=?", (nuevo_p, pagado, date.today(), r['id']))
                conn.commit(); st.rerun()
            if c_p2.button("🗑️ Borrar Cuota", key=f"del_c_{r['id']}"):
                conn.execute("DELETE FROM deudas WHERE id=?", (r['id'],))
                conn.commit(); st.rerun()
    conn.close()

# ==========================================
# 🚨 SECCIÓN 4: MOROSOS
# ==========================================
elif menu == "🚨 4. Morosos":
    st.header("Reporte de Deudores")
    conn = conectar()
    df_morosos = pd.read_sql_query("""
        SELECT inq.nombre as Inquilino, i.tipo as Unidad, d.concepto as Concepto, d.mes_anio as Periodo,
               (d.monto_debe - d.monto_pago) as Saldo_Pendiente, inq.celular as WhatsApp
        FROM deudas d
        JOIN contratos c ON d.id_contrato = c.id
        JOIN inmuebles i ON c.id_inmueble = i.id
        JOIN inquilinos inq ON c.id_inquilino = inq.id
        WHERE d.pagado = 0
    """, conn)
    conn.close()
    
    if not df_morosos.empty:
        df_morosos['Saldo_Pendiente'] = df_morosos['Saldo_Pendiente'].apply(fmt_moneda)
        st.dataframe(df_morosos, use_container_width=True, hide_index=True)
    else: st.success("¡Excelente! No hay moras registradas.")

# ==========================================
# 📊 SECCIÓN 5: CAJA
# ==========================================
elif menu == "📊 5. Caja":
    st.header("Resumen de Ingresos")
    c1, c2 = st.columns(2)
    f_desde = c1.date_input("Desde", date.today() - timedelta(days=30))
    f_hasta = c2.date_input("Hasta", date.today())
    
    conn = conectar()
    df_caja = pd.read_sql_query("""
        SELECT fecha_cobro as Fecha, concepto as Detalle, monto_pago as Importe
        FROM deudas WHERE pagado = 1 AND fecha_cobro BETWEEN ? AND ?
    """, conn, params=(f_desde, f_hasta))
    conn.close()
    
    if not df_caja.empty:
        total = df_caja['Importe'].sum()
        st.metric("Total Recaudado en el periodo", fmt_moneda(total))
        df_caja['Importe'] = df_caja['Importe'].apply(fmt_moneda)
        st.table(df_caja)
    else: st.warning("No hay cobros registrados en este rango de fechas.")

# ==========================================
# ⚙️ SECCIÓN 6: MAESTROS (Con EDICIÓN de unidades)
# ==========================================
elif menu == "⚙️ 6. Maestros":
    st.header("Administración de Maestros")
    t1, t2, t3, t4, t5 = st.tabs(["👤 Inquilinos", "🏢 Bloques", "🏠 Unidades", "📝 Contratos", "🚀 Procesos"])
    
    with t1: # Inquilinos
        con = conectar()
        col_in1, col_in2 = st.columns(2)
        with col_in1:
            st.write("### ➕ Nuevo Inquilino")
            with st.form("f_in"):
                n = st.text_input("Nombre Completo")
                w = st.text_input("WhatsApp")
                if st.form_submit_button("Guardar"):
                    con.execute("INSERT INTO inquilinos (nombre, celular) VALUES (?,?)", (n, w))
                    con.commit(); st.rerun()
        with col_in2:
            st.write("### 🗑️ Borrar Inquilino")
            inqs = pd.read_sql_query("SELECT * FROM inquilinos", con)
            if not inqs.empty:
                id_i = st.selectbox("Seleccionar", inqs['id'].tolist(), format_func=lambda x: inqs[inqs['id']==x]['nombre'].values[0])
                if st.button("ELIMINAR"):
                    con.execute("DELETE FROM inquilinos WHERE id=?", (id_i,))
                    con.commit(); st.rerun()
        con.close()

    with t2: # Bloques
        con = conectar()
        col_b1, col_b2 = st.columns(2)
        with col_b1:
            st.write("### 🏢 Nuevo Bloque")
            nb = st.text_input("Ej: Torre A, Planta Baja")
            if st.button("Guardar Bloque"):
                con.execute("INSERT INTO bloques (nombre) VALUES (?)", (nb,))
                con.commit(); st.rerun()
        with col_b2:
            st.write("### 🗑️ Borrar Bloque")
            bls = pd.read_sql_query("SELECT * FROM bloques", con)
            if not bls.empty:
                id_b = st.selectbox("Bloque a eliminar", bls['id'].tolist(), format_func=lambda x: bls[bls['id']==x]['nombre'].values[0])
                if st.button("ELIMINAR BLOQUE"):
                    con.execute("DELETE FROM bloques WHERE id=?", (id_b,))
                    con.commit(); st.rerun()
        con.close()

    with t3: # UNIDADES (CARGA Y EDICIÓN)
        con = conectar()
        st.write("### 🏠 Gestión de Unidades")
        col_u1, col_u2 = st.columns(2)
        
        with col_u1:
            st.write("#### ➕ Cargar Nueva")
            bls = pd.read_sql_query("SELECT * FROM bloques", con)
            if not bls.empty:
                with st.form("f_u_new"):
                    idb = st.selectbox("Bloque", bls['id'].tolist(), format_func=lambda x: bls[bls['id']==x]['nombre'].values[0])
                    tp = st.text_input("Nombre/Nro de Unidad")
                    p1, p2, p3 = st.columns(3)
                    pr = p1.text_input("Alquiler")
                    co = p2.text_input("Contrato")
                    de = p3.text_input("Depósito")
                    if st.form_submit_button("Guardar Unidad"):
                        con.execute("INSERT INTO inmuebles (id_bloque, tipo, precio_alquiler, costo_contrato, deposito_base) VALUES (?,?,?,?,?)",
                                    (idb, tp, limpiar_monto(pr), limpiar_monto(co), limpiar_monto(de)))
                        con.commit(); st.rerun()
        
        with col_u2:
            st.write("#### ✏️ Editar / 🗑️ Borrar")
            inms = pd.read_sql_query("SELECT i.id, b.nombre || ' - ' || i.tipo as ref, i.precio_alquiler, i.costo_contrato, i.deposito_base FROM inmuebles i JOIN bloques b ON i.id_bloque=b.id", con)
            if not inms.empty:
                sel_u = st.selectbox("Seleccionar Unidad", inms['id'].tolist(), format_func=lambda x: inms[inms['id']==x]['ref'].values[0])
                u_data = inms[inms['id']==sel_u].iloc[0]
                
                with st.form("f_u_edit"):
                    e_pr = st.text_input("Nuevo Alquiler", value=str(int(u_data['precio_alquiler'])))
                    e_co = st.text_input("Nuevo Costo Contrato", value=str(int(u_data['costo_contrato'])))
                    e_de = st.text_input("Nuevo Depósito", value=str(int(u_data['deposito_base'])))
                    col_e1, col_e2 = st.columns(2)
                    if col_e1.form_submit_button("ACTUALIZAR"):
                        con.execute("UPDATE inmuebles SET precio_alquiler=?, costo_contrato=?, deposito_base=? WHERE id=?", 
                                    (limpiar_monto(e_pr), limpiar_monto(e_co), limpiar_monto(e_de), sel_u))
                        con.commit(); st.rerun()
                if st.button("🗑️ ELIMINAR ESTA UNIDAD"):
                    con.execute("DELETE FROM inmuebles WHERE id=?", (sel_u,))
                    con.commit(); st.rerun()
        con.close()

    with t4: # Contratos
        con = conectar()
        st.write("### 🗑️ Gestión de Contratos")
        cons = pd.read_sql_query("""
            SELECT c.id, inq.nombre || ' - ' || i.tipo as ref 
            FROM contratos c JOIN inquilinos inq ON c.id_inquilino=inq.id 
            JOIN inmuebles i ON c.id_inmueble=i.id
        """, con)
        if not cons.empty:
            id_c = st.selectbox("Contrato a eliminar", cons['id'].tolist(), format_func=lambda x: cons[cons['id']==x]['ref'].values[0])
            st.warning("Cuidado: Al borrar el contrato se eliminarán sus cuotas pendientes.")
            if st.button("ELIMINAR CONTRATO"):
                con.execute("DELETE FROM deudas WHERE id_contrato=?", (id_c,))
                con.execute("DELETE FROM contratos WHERE id=?", (id_c,))
                con.commit(); st.rerun()
        con.close()

    with t5: # Procesos
        st.write("### 🚀 Generar Cuotas Masivas")
        mes = st.text_input("Mes y Año (Ej: Junio 2025)")
        if st.button("GENERAR ALQUILERES PARA TODOS"):
            con = conectar()
            activos = pd.read_sql_query("SELECT id, monto_alquiler FROM contratos WHERE activo=1", con)
            for _, c in activos.iterrows():
                con.execute("INSERT INTO deudas (id_contrato, concepto, mes_anio, monto_debe) VALUES (?, 'Alquiler', ?, ?)", 
                            (c['id'], mes, c['monto_alquiler']))
            con.commit(); con.close(); st.success(f"Cuotas de {mes} generadas con éxito.")
