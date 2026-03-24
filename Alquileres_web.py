import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, date, timedelta
import urllib.parse
import os

# ==========================================
# 1. CONFIGURACIÓN Y MOTOR DE BASE DE DATOS
# ==========================================
st.set_page_config(page_title="Inmobiliaria Pro", layout="wide")

def conectar():
    return sqlite3.connect('datos_alquileres.db', check_same_thread=False, timeout=20)

def fmt_moneda(valor):
    try: 
        # Formato con separador de miles: 100.000
        return f"$ {int(float(valor or 0)):,}".replace(",", ".")
    except: 
        return "$ 0"

def limpiar_monto(texto):
    if not texto: return 0
    try: 
        # Convertimos a entero para evitar decimales en la base
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
# 2. MENÚ LATERAL
# ==========================================
with st.sidebar:
    st.title("🏢 Inmobiliaria Pro")
    if st.button("🚨 REINICIAR TODA LA BASE (BORRADO TOTAL)"):
        if os.path.exists('datos_alquileres.db'):
            os.remove('datos_alquileres.db')
        inicializar_db()
        st.cache_data.clear()
        st.success("Base reseteada a cero.")
        st.rerun()
    st.divider()
    menu = st.radio("Navegación:", 
                    ["🏠 1. Inventario", "📝 2. Nuevo Contrato", "💰 3. Cobranzas", 
                     "🚨 4. Morosos", "📊 5. Caja", "⚙️ 6. Maestros"])

# ==========================================
# 3. FUNCIONALIDADES PRINCIPALES
# ==========================================

if menu == "🏠 1. Inventario":
    st.subheader("Estado de Unidades y Disponibilidad")
    conn = conectar()
    query = """
        SELECT i.id, b.nombre as Bloque, i.tipo as Unidad, 
               i.precio_alquiler, i.costo_contrato, i.deposito_base,
               c.fecha_inicio, c.fecha_fin, c.activo
        FROM inmuebles i
        JOIN bloques b ON i.id_bloque = b.id
        LEFT JOIN contratos c ON i.id = c.id_inmueble AND c.activo = 1
    """
    df = pd.read_sql_query(query, conn)
    conn.close()

    if not df.empty:
        def calc_sit(row):
            hoy = date.today()
            if pd.isna(row['fecha_inicio']) or row['activo'] == 0: 
                return "Libre", "LIBRE HOY"
            try:
                f_fin = pd.to_datetime(row['fecha_fin']).date()
                if hoy <= f_fin: return "OCUPADO", f_fin.strftime('%d/%m/%Y')
                else: return "VENCIDO", "LIBRE HOY"
            except: return "Libre", "LIBRE HOY"

        df[['Situación', 'Disponible Desde']] = df.apply(lambda x: pd.Series(calc_sit(x)), axis=1)
        df['Alquiler'] = df['precio_alquiler'].apply(fmt_moneda)
        
        def color_sit(val):
            # Verde para libre, Rojo para ocupado
            color = '#28a745' if val == "Libre" else '#dc3545'
            return f'color: {color}; font-weight: bold'

        st.dataframe(df[["Bloque", "Unidad", "Situación", "Disponible Desde", "Alquiler"]].style.applymap(color_sit, subset=['Situación']), 
                     use_container_width=True, hide_index=True)
    else: st.info("Cargue unidades en Maestros.")

elif menu == "📝 2. Nuevo Contrato":
    st.subheader("Alta de Alquiler")
    conn = conectar()
    inm_db = pd.read_sql_query("SELECT * FROM inmuebles", conn)
    inq_db = pd.read_sql_query("SELECT * FROM inquilinos", conn)
    if not inm_db.empty and not inq_db.empty:
        with st.form("f_con"):
            c1, c2 = st.columns(2)
            id_inm = c1.selectbox("Unidad", inm_db['id'].tolist(), format_func=lambda x: f"{inm_db[inm_db['id']==x]['tipo'].values[0]}")
            id_inq = c2.selectbox("Inquilino", inq_db['id'].tolist(), format_func=lambda x: inq_db[inq_db['id']==x]['nombre'].values[0])
            f_ini = c1.date_input("Inicio", date.today())
            meses = c2.number_input("Meses", min_value=1, value=6)
            f_fin = f_ini + timedelta(days=meses * 30)
            val_ref = inm_db[inm_db['id'] == id_inm].iloc[0]
            m_alq = c1.text_input("Alquiler Mensual", value=str(int(val_ref['precio_alquiler'])))
            if st.form_submit_button("Grabar Contrato"):
                conn.execute("INSERT INTO contratos (id_inmueble, id_inquilino, fecha_inicio, fecha_fin, meses, activo, monto_alquiler) VALUES (?,?,?,?,?,1,?)", 
                            (id_inm, id_inq, f_ini, f_fin, meses, limpiar_monto(m_alq)))
                conn.commit(); st.success("Contrato grabado"); st.rerun()
    else: st.warning("Faltan datos en Maestros.")
    conn.close()

elif menu == "💰 3. Cobranzas":
    st.subheader("Gestión de Cobros")
    conn = conectar()
    df_c = pd.read_sql_query("""
        SELECT d.id, i.tipo, inq.nombre, d.monto_debe, d.monto_pago, inq.celular, d.concepto, d.mes_anio
        FROM deudas d JOIN contratos c ON d.id_contrato=c.id
        JOIN inmuebles i ON c.id_inmueble=i.id JOIN inquilinos inq ON c.id_inquilino=inq.id
        WHERE d.pagado = 0
    """, conn)
    for _, row in df_c.iterrows():
        with st.expander(f"{row['tipo']} - {row['nombre']} ({row['mes_anio']})"):
            saldo = row['monto_debe'] - row['monto_pago']
            st.write(f"Deuda Total: {fmt_moneda(row['monto_debe'])}")
            pago_t = st.text_input(f"Monto a cobrar", value=str(int(saldo)), key=f"c_{row['id']}")
            col_p1, col_p2 = st.columns(2)
            if col_p1.button("✅ Confirmar Pago", key=f"b_{row['id']}"):
                p = limpiar_monto(pago_t)
                conn.execute("UPDATE deudas SET monto_pago=?, pagado=?, fecha_cobro=? WHERE id=?", 
                             (row['monto_pago']+p, 1 if (row['monto_pago']+p)>=row['monto_debe'] else 0, date.today(), row['id']))
                conn.commit()
                st.rerun()
            if col_p2.button("🗑️ Borrar Cuota", key=f"del_d_{row['id']}"):
                conn.execute("DELETE FROM deudas WHERE id=?", (row['id'],))
                conn.commit(); st.rerun()
    conn.close()

elif menu == "🚨 4. Morosos":
    st.subheader("Deudores")
    conn = conectar()
    df_m = pd.read_sql_query("""
        SELECT inq.nombre as Inquilino, i.tipo as Unidad, d.mes_anio as Mes, 
        (d.monto_debe - d.monto_pago) as Saldo 
        FROM deudas d 
        JOIN contratos c ON d.id_contrato=c.id 
        JOIN inmuebles i ON c.id_inmueble=i.id 
        JOIN inquilinos inq ON c.id_inquilino=inq.id 
        WHERE d.pagado=0
    """, conn)
    if not df_m.empty: 
        df_m['Saldo'] = df_m['Saldo'].apply(fmt_moneda)
        st.table(df_m)
    else: st.success("Al día.")
    conn.close()

# ==========================================
# 4. MAESTROS (CON FUNCIONES DE BORRADO)
# ==========================================
elif menu == "⚙️ 6. Maestros":
    st.subheader("Administración (MAESTROS)")
    t1, t2, t3, t4, t5 = st.tabs(["👤 Inquilinos", "🏢 Bloques", "🏠 Unidades", "📝 Contratos", "⚡ Procesos"])
    
    with t1:
        con = conectar()
        col1, col2 = st.columns(2)
        with col1:
            st.write("### ➕ Nuevo Inquilino")
            with st.form("fi"):
                n, t = st.text_input("Nombre"), st.text_input("WhatsApp")
                if st.form_submit_button("Guardar"):
                    con.execute("INSERT INTO inquilinos (nombre, celular) VALUES (?,?)", (n, t))
                    con.commit(); st.rerun()
        with col2:
            st.write("### 🗑️ Borrar Inquilino")
            inqs = pd.read_sql_query("SELECT * FROM inquilinos", con)
            if not inqs.empty:
                id_i = st.selectbox("Seleccionar Inquilino", inqs['id'].tolist(), format_func=lambda x: inqs[inqs['id']==x]['nombre'].values[0])
                if st.button("🗑️ ELIMINAR INQUILINO"):
                    con.execute("DELETE FROM inquilinos WHERE id=?", (id_i,))
                    con.commit(); con.close(); st.rerun()
        con.close()

    with t2:
        con = conectar()
        col_b1, col_b2 = st.columns(2)
        with col_b1:
            st.write("### ➕ Nuevo Bloque")
            n_b = st.text_input("Nombre del Bloque (Ej: Torre A)")
            if st.button("Guardar Bloque"):
                con.execute("INSERT INTO bloques (nombre) VALUES (?)", (n_b,))
                con.commit(); st.rerun()
        with col_b2:
            st.write("### 🗑️ Borrar Bloque")
            bls = pd.read_sql_query("SELECT * FROM bloques", con)
            if not bls.empty:
                id_b = st.selectbox("Seleccionar Bloque", bls['id'].tolist(), format_func=lambda x: bls[bls['id']==x]['nombre'].values[0])
                if st.button("🗑️ ELIMINAR BLOQUE"):
                    con.execute("DELETE FROM bloques WHERE id=?", (id_b,))
                    con.commit(); con.close(); st.rerun()
        con.close()

    with t3:
        con = conectar()
        col_u1, col_u2 = st.columns(2)
        with col_u1:
            st.write("### ➕ Nueva Unidad")
            bls = pd.read_sql_query("SELECT * FROM bloques", con)
            if not bls.empty:
                with st.form("fu"):
                    idb = st.selectbox("Bloque", bls['id'].tolist(), format_func=lambda x: bls[bls['id']==x]['nombre'].values[0])
                    tp = st.text_input("Unidad (Ej: Depto 101)")
                    pr = st.text_input("Precio Alquiler")
                    if st.form_submit_button("Guardar Unidad"):
                        con.execute("INSERT INTO inmuebles (id_bloque, tipo, precio_alquiler) VALUES (?,?,?)", (idb, tp, limpiar_monto(pr)))
                        con.commit(); st.rerun()
        with col_u2:
            st.write("### 🗑️ Borrar Unidad")
            inms = pd.read_sql_query("SELECT i.id, b.nombre || ' - ' || i.tipo as ref FROM inmuebles i JOIN bloques b ON i.id_bloque=b.id", con)
            if not inms.empty:
                id_u = st.selectbox("Seleccionar Unidad", inms['id'].tolist(), format_func=lambda x: inms[inms['id']==x]['ref'].values[0])
                if st.button("🗑️ ELIMINAR UNIDAD"):
                    con.execute("DELETE FROM inmuebles WHERE id=?", (id_u,))
                    con.commit(); con.close(); st.rerun()
        con.close()

    with t4:
        st.write("### 🗑️ Borrar Contrato")
        con = conectar()
        cons = pd.read_sql_query("""
            SELECT c.id, inq.nombre || ' - ' || i.tipo as ref 
            FROM contratos c JOIN inquilinos inq ON c.id_inquilino=inq.id
            JOIN inmuebles i ON c.id_inmueble=i.id
        """, con)
        if not cons.empty:
            id_c = st.selectbox("Seleccionar Contrato", cons['id'].tolist(), format_func=lambda x: cons[cons['id']==x]['ref'].values[0])
            if st.button("❌ ELIMINAR CONTRATO (Y SUS CUOTAS)"):
                con.execute("DELETE FROM deudas WHERE id_contrato=?", (id_c,))
                con.execute("DELETE FROM contratos WHERE id=?", (id_c,))
                con.commit(); con.close(); st.rerun()
        con.close()

    with t5:
        st.write("### Procesos Masivos")
        mes = st.text_input("Mes/Año (Ej: Mayo 2026)")
        if st.button("🚀 Generar Cuotas de Alquiler"):
            con = conectar()
            activos = pd.read_sql_query("SELECT id, monto_alquiler FROM contratos WHERE activo=1", con)
            for _, c in activos.iterrows():
                con.execute("INSERT INTO deudas (id_contrato, concepto, mes_anio, monto_debe) VALUES (?,?,?,?)", (c['id'], "Alquiler", mes, c['monto_alquiler']))
            con.commit(); con.close(); st.success("Cuotas generadas"); st.rerun()
