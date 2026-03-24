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
# 🏠 SECCIÓN 1: INVENTARIO
# ==========================================
if menu == "🏠 1. Inventario":
    st.header("Estado de Unidades")
    conn = conectar()
    df = pd.read_sql_query("""
        SELECT i.id, b.nombre as Bloque, i.tipo as Unidad, i.precio_alquiler, i.costo_contrato, i.deposito_base,
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
        st.table(df[["Bloque", "Unidad", "Estado", "Disponible", "precio_alquiler"]].rename(columns={'precio_alquiler': 'Precio'}))
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
            m_alq = c1.text_input("Alquiler", value=str(int(datos_u['precio_alquiler'])))
            m_con = c2.text_input("Contrato", value=str(int(datos_u['costo_contrato'])))
            m_dep = c1.text_input("Depósito", value=str(int(datos_u['deposito_base'])))
            
            if st.form_submit_button("Guardar Contrato"):
                f_fin = f_ini + timedelta(days=meses*30)
                conn.execute("INSERT INTO contratos (id_inmueble, id_inquilino, fecha_inicio, fecha_fin, meses, activo, monto_alquiler, monto_contrato, monto_deposito) VALUES (?,?,?,?,?,1,?,?,?)",
                             (sel_inm, sel_inq, f_ini, f_fin, meses, limpiar_monto(m_alq), limpiar_monto(m_con), limpiar_monto(m_dep)))
                conn.commit(); st.success("Contrato creado"); st.rerun()
    conn.close()

# ==========================================
# 💰 SECCIÓN 3: COBRANZAS
# ==========================================
elif menu == "💰 3. Cobranzas":
    st.header("Cobro de Cuotas")
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
            pago = st.text_input(f"Monto a pagar", value=str(int(saldo)), key=f"p_{r['id']}")
            if st.button("Confirmar Pago", key=f"btn_{r['id']}"):
                nuevo_p = r['monto_pago'] + limpiar_monto(pago)
                pagado = 1 if nuevo_p >= r['monto_debe'] else 0
                conn.execute("UPDATE deudas SET monto_pago=?, pagado=?, fecha_cobro=? WHERE id=?", (nuevo_p, pagado, date.today(), r['id']))
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
    else: st.success("No hay deudas pendientes.")

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
        st.metric("Total Recaudado", fmt_moneda(total))
        df_caja['Importe'] = df_caja['Importe'].apply(fmt_moneda)
        st.table(df_caja)
    else: st.warning("No hay cobros en este rango de fechas.")

# ==========================================
# ⚙️ SECCIÓN 6: MAESTROS (GESTIÓN Y BORRADO)
# ==========================================
elif menu == "⚙️ 6. Maestros":
    st.header("Configuración del Sistema")
    t1, t2, t3, t4, t5 = st.tabs(["👤 Inquilinos", "🏢 Bloques", "🏠 Unidades", "📝 Contratos", "🚀 Procesos"])
    
    with t1: # Inquilinos
        con = conectar()
        st.write("### 🗑️ Borrar Inquilino")
        inqs = pd.read_sql_query("SELECT * FROM inquilinos", con)
        if not inqs.empty:
            id_i = st.selectbox("Seleccionar", inqs['id'].tolist(), format_func=lambda x: inqs[inqs['id']==x]['nombre'].values[0], key="del_inq")
            if st.button("ELIMINAR INQUILINO"):
                con.execute("DELETE FROM inquilinos WHERE id=?", (id_i,))
                con.commit(); st.rerun()
        con.close()

    with t2: # Bloques
        con = conectar()
        st.write("### 🏢 Gestión de Bloques")
        nb = st.text_input("Nuevo Bloque")
        if st.button("Guardar Bloque"):
            con.execute("INSERT INTO bloques (nombre) VALUES (?)", (nb,))
            con.commit(); st.rerun()
        
        bls = pd.read_sql_query("SELECT * FROM bloques", con)
        if not bls.empty:
            id_b = st.selectbox("Borrar Bloque", bls['id'].tolist(), format_func=lambda x: bls[bls['id']==x]['nombre'].values[0])
            if st.button("ELIMINAR BLOQUE"):
                con.execute("DELETE FROM bloques WHERE id=?", (id_b,))
                con.commit(); st.rerun()
        con.close()

    with t3: # Unidades
        con = conectar()
        st.write("### ➕ Nueva Unidad")
        bls = pd.read_sql_query("SELECT * FROM bloques", con)
        if not bls.empty:
            with st.form("f_u"):
                idb = st.selectbox("Bloque", bls['id'].tolist(), format_func=lambda x: bls[bls['id']==x]['nombre'].values[0])
                tp = st.text_input("Nombre Unidad")
                p1, p2, p3 = st.columns(3)
                pr = p1.text_input("Alquiler")
                co = p2.text_input("Contrato")
                de = p3.text_input("Depósito")
                if st.form_submit_button("Guardar"):
                    con.execute("INSERT INTO inmuebles (id_bloque, tipo, precio_alquiler, costo_contrato, deposito_base) VALUES (?,?,?,?,?)",
                                (idb, tp, limpiar_monto(pr), limpiar_monto(co), limpiar_monto(de)))
                    con.commit(); st.rerun()
        con.close()

    with t4: # Borrar Contratos
        con = conectar()
        st.write("### 🗑️ Borrar Contrato")
        cons = pd.read_sql_query("SELECT c.id, inq.nombre || ' - ' || i.tipo as ref FROM contratos c JOIN inquilinos inq ON c.id_inquilino=inq.id JOIN inmuebles i ON c.id_inmueble=i.id", con)
        if not cons.empty:
            id_c = st.selectbox("Contrato a eliminar", cons['id'].tolist(), format_func=lambda x: cons[cons['id']==x]['ref'].values[0])
            if st.button("ELIMINAR CONTRATO"):
                con.execute("DELETE FROM deudas WHERE id_contrato=?", (id_c,))
                con.execute("DELETE FROM contratos WHERE id=?", (id_c,))
                con.commit(); st.rerun()
        con.close()

    with t5: # Generar Cuotas
        st.write("### 🚀 Generar Cuotas Mensuales")
        mes = st.text_input("Mes/Año (Ej: Marzo 2026)")
        if st.button("GENERAR PARA TODOS LOS ACTIVOS"):
            con = conectar()
            activos = pd.read_sql_query("SELECT id, monto_alquiler FROM contratos WHERE activo=1", con)
            for _, c in activos.iterrows():
                con.execute("INSERT INTO deudas (id_contrato, concepto, mes_anio, monto_debe) VALUES (?, 'Alquiler', ?, ?)", (c['id'], mes, c['monto_alquiler']))
            con.commit(); con.close(); st.success("Cuotas generadas.")
