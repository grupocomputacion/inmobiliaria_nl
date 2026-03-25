import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, date, timedelta
import os
import urllib.parse

# ==========================================
# 1. CONFIGURACIÓN E IDENTIDAD VISUAL
# ==========================================
st.set_page_config(
    page_title="NL Propiedades - Gestión", 
    page_icon="🏠", 
    layout="wide", 
    initial_sidebar_state="expanded"
)

# Estilo Dorado y Negro
st.markdown("""
    <style>
    .stButton>button { background-color: #D4AF37; color: black; border-radius: 5px; font-weight: bold; width: 100%; }
    .stButton>button:hover { background-color: #B8860B; color: white; }
    h1, h2, h3, h4 { color: #D4AF37; }
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 2. MOTOR DE BASE DE DATOS Y MIGRACIONES
# ==========================================
def conectar():
    return sqlite3.connect('datos_alquileres.db', check_same_thread=False, timeout=20)

def inicializar_db():
    conn = conectar()
    c = conn.cursor()
    # Creación de tablas base
    c.execute("CREATE TABLE IF NOT EXISTS bloques (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT UNIQUE)")
    c.execute("""CREATE TABLE IF NOT EXISTS inmuebles (
        id INTEGER PRIMARY KEY AUTOINCREMENT, id_bloque INTEGER, tipo TEXT, 
        precio_alquiler INTEGER, costo_contrato INTEGER, deposito_base INTEGER, UNIQUE(id_bloque, tipo))""")
    c.execute("CREATE TABLE IF NOT EXISTS inquilinos (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT)")
    c.execute("""CREATE TABLE IF NOT EXISTS contratos (
        id INTEGER PRIMARY KEY AUTOINCREMENT, id_inmueble INTEGER, id_inquilino INTEGER, 
        fecha_inicio DATE, fecha_fin DATE, meses INTEGER, activo INTEGER DEFAULT 1, 
        monto_alquiler INTEGER, monto_contrato INTEGER, monto_deposito INTEGER)""")
    c.execute("""CREATE TABLE IF NOT EXISTS deudas (
        id INTEGER PRIMARY KEY AUTOINCREMENT, id_contrato INTEGER, concepto TEXT, 
        mes_anio TEXT, monto_debe INTEGER, monto_pago INTEGER DEFAULT 0, pagado INTEGER DEFAULT 0, fecha_cobro DATE)""")

    # Migración de columnas (Seguridad de datos)
    migraciones = {
        "inquilinos": [("celular", "TEXT"), ("dni", "TEXT"), ("direccion", "TEXT"), ("emergencia_contacto", "TEXT"), ("procedencia", "TEXT"), ("grupo", "TEXT")],
        "inmuebles": [("precio_alquiler", "INTEGER"), ("costo_contrato", "INTEGER"), ("deposito_base", "INTEGER")]
    }
    for tabla, columnas in migraciones.items():
        cursor = c.execute(f"PRAGMA table_info({tabla})")
        existentes = [row[1] for row in cursor.fetchall()]
        for col, tipo in columnas:
            if col not in existentes:
                try: c.execute(f"ALTER TABLE {tabla} ADD COLUMN {col} {tipo}")
                except: pass
    conn.commit()
    conn.close()

inicializar_db()

# Utilidades
def fmt_moneda(valor):
    try: return f"$ {int(float(valor or 0)):,}".replace(",", ".")
    except: return "$ 0"

def limpiar_monto(texto):
    if not texto: return 0
    try: return int(float(str(texto).replace('$', '').replace('.', '').replace(',', '').strip()))
    except: return 0

# ==========================================
# 3. BARRA LATERAL (MENÚ)
# ==========================================
with st.sidebar:
    try: st.image("logo.jpg", use_container_width=True)
    except: st.title("NL PROPIEDADES")
    st.divider()
    
    opciones_menu = ["🏠 1. Inventario", "📝 2. Nuevo Contrato", "💰 3. Cobranzas", "🚨 4. Morosos", "📊 5. Caja", "⚙️ 6. Maestros"]
    menu = st.radio("Navegación:", opciones_menu)
    
    st.divider()
    if st.button("🚨 RESETEAR (SÓLO DESARROLLO)"):
        if os.path.exists('datos_alquileres.db'): os.remove('datos_alquileres.db')
        inicializar_db()
        st.rerun()

# ==========================================
# 4. LÓGICA DE SECCIONES (BLOQUES INDEPENDIENTES)
# ==========================================

# --- SECCIÓN 1: INVENTARIO ---
if menu == "🏠 1. Inventario":
    st.header("Inventario de Unidades")
    conn = conectar()
    query = """
        SELECT b.nombre as Bloque, i.tipo as Unidad, i.precio_alquiler, i.costo_contrato, i.deposito_base,
               MAX(c.fecha_fin) as Vencimiento, MAX(c.activo) as ocupado
        FROM inmuebles i JOIN bloques b ON i.id_bloque = b.id
        LEFT JOIN contratos c ON i.id = c.id_inmueble AND c.activo = 1
        GROUP BY i.id
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    if not df.empty:
        df['Estado'] = df['ocupado'].apply(lambda x: "🔴 OCUPADO" if x == 1 else "🟢 LIBRE")
        df['Alquiler'] = df['precio_alquiler'].apply(fmt_moneda)
        df['Contrato'] = df['costo_contrato'].apply(fmt_moneda)
        df['Depósito'] = df['deposito_base'].apply(fmt_moneda)
        st.dataframe(df[["Bloque", "Unidad", "Estado", "Vencimiento", "Alquiler", "Contrato", "Depósito"]], use_container_width=True, hide_index=True)
    else: st.info("Sin unidades registradas.")

# --- SECCIÓN 2: NUEVO CONTRATO ---
elif menu == "📝 2. Nuevo Contrato":
    st.header("Alta de Alquiler")
    conn = conectar()
    inm = pd.read_sql_query("SELECT i.id, b.nombre || ' - ' || i.tipo as ref, i.precio_alquiler, i.costo_contrato, i.deposito_base FROM inmuebles i JOIN bloques b ON i.id_bloque=b.id", conn)
    inq = pd.read_sql_query("SELECT id, nombre FROM inquilinos", conn)
    if not inm.empty and not inq.empty:
        with st.form("f_contrato", clear_on_submit=True):
            c1, c2 = st.columns(2)
            id_u = c1.selectbox("Unidad", inm['id'].tolist(), format_func=lambda x: inm[inm['id']==x]['ref'].values[0])
            id_i = c2.selectbox("Inquilino", inq['id'].tolist(), format_func=lambda x: inq[inq['id']==x]['nombre'].values[0])
            f_ini = c1.date_input("Inicio", date.today())
            meses = c2.number_input("Meses", 1, 60, 6)
            
            u_data = inm[inm['id']==id_u].iloc[0]
            m_alq = c1.text_input("Monto Alquiler", value=str(int(u_data['precio_alquiler'] or 0)))
            m_con = c2.text_input("Monto Contrato", value=str(int(u_data['costo_contrato'] or 0)))
            m_dep = st.text_input("Monto Depósito", value=str(int(u_data['deposito_base'] or 0)))
            
            if st.form_submit_button("GRABAR CONTRATO"):
                f_fin = f_ini + timedelta(days=meses*30)
                cur = conn.cursor()
                cur.execute("INSERT INTO contratos (id_inmueble, id_inquilino, fecha_inicio, fecha_fin, meses, activo, monto_alquiler, monto_contrato, monto_deposito) VALUES (?,?,?,?,?,?,?,?)", (id_u, id_i, f_ini, f_fin, meses, limpiar_monto(m_alq), limpiar_monto(m_con), limpiar_monto(m_dep)))
                id_c = cur.lastrowid
                mes_txt = f_ini.strftime("%m/%Y")
                cur.executemany("INSERT INTO deudas (id_contrato, concepto, mes_anio, monto_debe) VALUES (?,?,?,?)", [(id_c, "Contrato", mes_txt, limpiar_monto(m_con)), (id_c, "Depósito", mes_txt, limpiar_monto(m_dep)), (id_c, "Mes 1", mes_txt, limpiar_monto(m_alq))])
                conn.commit()
                st.success("Guardado y deudas generadas.")
                st.rerun()
    else: st.warning("Cargue Inquilinos y Unidades primero.")
    conn.close()

# --- SECCIÓN 3: COBRANZAS ---
elif menu == "💰 3. Cobranzas":
    st.header("Gestión de Cobros")
    conn = conectar()
    deudas = pd.read_sql_query("""SELECT d.id, inq.nombre, i.tipo, d.concepto, d.mes_anio, d.monto_debe, d.monto_pago, inq.celular FROM deudas d JOIN contratos c ON d.id_contrato=c.id JOIN inmuebles i ON c.id_inmueble=i.id JOIN inquilinos inq ON c.id_inquilino=inq.id WHERE d.pagado = 0""", conn)
    if not deudas.empty:
        for _, r in deudas.iterrows():
            with st.expander(f"💰 {r['nombre']} - {r['tipo']} ({r['concepto']})"):
                saldo = r['monto_debe'] - r['monto_pago']
                pago = st.text_input(f"Monto a cobrar", value=str(int(saldo)), key=f"p_{r['id']}")
                col1, col2 = st.columns(2)
                if col1.button("Confirmar Pago", key=f"btn_{r['id']}"):
                    nuevo_p = r['monto_pago'] + limpiar_monto(pago)
                    conn.execute("UPDATE deudas SET monto_pago=?, pagado=?, fecha_cobro=? WHERE id=?", (nuevo_p, 1 if nuevo_p>=r['monto_debe'] else 0, date.today(), r['id']))
                    conn.commit()
                    # WhatsApp
                    msg = urllib.parse.quote(f"✅ RECIBO NL PROPIEDADES\nUnidad: {r['tipo']}\nAbonado: {fmt_moneda(limpiar_monto(pago))}\nSaldo: {fmt_moneda(saldo - limpiar_monto(pago))}")
                    st.markdown(f'<a href="https://wa.me/{r["celular"]}?text={msg}" target="_blank">📲 Enviar WhatsApp</a>', unsafe_allow_html=True)
                    st.rerun()
                if col2.button("Borrar Cuota", key=f"del_{r['id']}"):
                    conn.execute("DELETE FROM deudas WHERE id=?", (r['id'],)); conn.commit(); st.rerun()
    else: st.info("Sin cuotas pendientes.")
    conn.close()

# --- SECCIÓN 4: MOROSOS ---
elif menu == "🚨 4. Morosos":
    st.header("Reporte de Morosidad")
    conn = conectar()
    df_m = pd.read_sql_query("""SELECT inq.nombre as Inquilino, i.tipo as Unidad, d.concepto as Concepto, d.mes_anio as Periodo, (d.monto_debe - d.monto_pago) as Saldo FROM deudas d JOIN contratos c ON d.id_contrato=c.id JOIN inmuebles i ON c.id_inmueble=i.id JOIN inquilinos inq ON c.id_inquilino=inq.id WHERE d.pagado=0""", conn)
    conn.close()
    if not df_m.empty:
        df_m['Saldo'] = df_m['Saldo'].apply(fmt_moneda)
        st.dataframe(df_m, use_container_width=True, hide_index=True)
    else: st.success("Al día.")

# --- SECCIÓN 5: CAJA ---
elif menu == "📊 5. Caja":
    st.header("Ingresos Realizados")
    conn = conectar()
    df_c = pd.read_sql_query("SELECT fecha_cobro as Fecha, concepto as Detalle, monto_pago as Importe FROM deudas WHERE pagado=1", conn)
    conn.close()
    if not df_c.empty:
        st.metric("Total Recaudado", fmt_moneda(df_c['Importe'].sum()))
        df_c['Importe'] = df_c['Importe'].apply(fmt_moneda)
        st.dataframe(df_c, use_container_width=True, hide_index=True)
    else: st.info("Caja vacía.")

# --- SECCIÓN 6: MAESTROS ---
elif menu == "⚙️ 6. Maestros":
    st.header("Administración")
    t1, t2, t3, t4, t5 = st.tabs(["👤 Inquilinos", "🏢 Bloques", "🏠 Unidades", "📝 Contratos", "🚀 Procesos"])
    
    with t1: # Inquilinos ABM
        con = conectar(); inqs_df = pd.read_sql_query("SELECT * FROM inquilinos", con); c1, c2 = st.columns(2)
        with c1:
            modo = st.radio("Acción Inquilino", ["Nuevo", "Editar"], horizontal=True)
            v_id, v_nom, v_cel, v_dni, v_pro, v_gru, v_dir, v_eme = None, "", "", "", "", "", "", ""
            if modo == "Editar" and not inqs_df.empty:
                sel_i = st.selectbox("Elegir:", inqs_df['id'].tolist(), format_func=lambda x: inqs_df[inqs_df['id']==x]['nombre'].values[0])
                f = inqs_df[inqs_df['id']==sel_i].iloc[0]
                v_id, v_nom, v_cel, v_dni, v_pro, v_gru, v_dir, v_eme = f['id'], f['nombre'], f['celular'], f['dni'], f['procedencia'], f['grupo'], f['direccion'], f['emergencia_contacto']
            with st.form("fi", clear_on_submit=True):
                f_nom = st.text_input("Nombre", value=v_nom); f_dni = st.text_input("DNI", value=v_dni)
                f_cel = st.text_input("WhatsApp", value=v_cel); f_pro = st.text_input("Procedencia", value=v_pro)
                f_gru = st.text_input("Grupo", value=v_gru); f_dir = st.text_input("Dirección", value=v_dir); f_eme = st.text_input("Emergencia", value=v_eme)
                if st.form_submit_button("Guardar"):
                    if modo == "Nuevo": con.execute("INSERT INTO inquilinos (nombre, celular, dni, procedencia, grupo, direccion, emergencia_contacto) VALUES (?,?,?,?,?,?,?)", (f_nom, f_cel, f_dni, f_pro, f_gru, f_dir, f_eme))
                    else: con.execute("UPDATE inquilinos SET nombre=?, celular=?, dni=?, procedencia=?, grupo=?, direccion=?, emergencia_contacto=? WHERE id=?", (f_nom, f_cel, f_dni, f_pro, f_gru, f_dir, f_eme, v_id))
                    con.commit(); st.rerun()
        with c2:
            st.write("### Borrar")
            if not inqs_df.empty:
                id_del = st.selectbox("Eliminar Inquilino", inqs_df['id'].tolist(), format_func=lambda x: inqs_df[inqs_df['id']==x]['nombre'].values[0], key="del_inq")
                if st.button("🗑️ Eliminar"): con.execute("DELETE FROM inquilinos WHERE id=?", (id_del,)); con.commit(); st.rerun()
        con.close()

    with t2: # Bloques
        con = conectar(); bls_df = pd.read_sql_query("SELECT * FROM bloques", con); c1, c2 = st.columns(2)
        with c1:
            nb = st.text_input("Nuevo Bloque")
            if st.button("Guardar Bloque"): con.execute("INSERT INTO bloques (nombre) VALUES (?)", (nb,)); con.commit(); st.rerun()
        with c2:
            if not bls_df.empty:
                id_b = st.selectbox("Borrar", bls_df['id'].tolist(), format_func=lambda x: bls_df[bls_df['id']==x]['nombre'].values[0])
                if st.button("🗑️ Borrar Bloque"): con.execute("DELETE FROM bloques WHERE id=?", (id_b,)); con.commit(); st.rerun()
        con.close()

    with t3: # Unidades
        con = conectar(); bls = pd.read_sql_query("SELECT * FROM bloques", con); unid_df = pd.read_sql_query("SELECT i.*, b.nombre as b_nom FROM inmuebles i JOIN bloques b ON i.id_bloque = b.id", con); c1, c2 = st.columns(2)
        with c1:
            modo_u = st.radio("Acción Unidad", ["Nuevo", "Editar"], horizontal=True)
            v_uid, v_utp, v_upr, v_uco, v_ude = None, "", "", "", ""
            if modo_u == "Editar" and not unid_df.empty:
                sel_u = st.selectbox("Unidad:", unid_df['id'].tolist(), format_func=lambda x: f"{unid_df[unid_df['id']==x]['b_nom'].values[0]} - {unid_df[unid_df['id']==x]['tipo'].values[0]}")
                fu = unid_df[unid_df['id']==sel_u].iloc[0]; v_uid, v_utp, v_upr, v_uco, v_ude = fu['id'], fu['tipo'], fu['precio_alquiler'], fu['costo_contrato'], fu['deposito_base']
            with st.form("fu", clear_on_submit=True):
                idb = st.selectbox("Bloque Unidad", bls['id'].tolist(), format_func=lambda x: bls[bls['id']==x]['nombre'].values[0])
                tp = st.text_input("Nombre Unidad", value=v_utp)
                p1 = st.text_input("Alquiler Sug.", value=str(v_upr)); p2 = st.text_input("Contrato Sug.", value=str(v_uco)); p3 = st.text_input("Depósito Sug.", value=str(v_ude))
                if st.form_submit_button("Guardar Unidad"):
                    if modo_u == "Nuevo": con.execute("INSERT INTO inmuebles (id_bloque, tipo, precio_alquiler, costo_contrato, deposito_base) VALUES (?,?,?,?,?)", (idb, tp, limpiar_monto(p1), limpiar_monto(p2), limpiar_monto(p3)))
                    else: con.execute("UPDATE inmuebles SET id_bloque=?, tipo=?, precio_alquiler=?, costo_contrato=?, deposito_base=? WHERE id=?", (idb, tp, limpiar_monto(p1), limpiar_monto(p2), limpiar_monto(p3), v_uid))
                    con.commit(); st.rerun()
        with c2:
            if not unid_df.empty:
                id_ud = st.selectbox("Borrar", unid_df['id'].tolist(), format_func=lambda x: f"{unid_df[unid_df['id']==x]['b_nom'].values[0]} - {unid_df[unid_df['id']==x]['tipo'].values[0]}", key="del_u")
                if st.button("🗑️ Eliminar Unidad"): con.execute("DELETE FROM inmuebles WHERE id=?", (id_ud,)); con.commit(); st.rerun()
        con.close()

    with t4: # Contratos
        con = conectar(); df_c = pd.read_sql_query("SELECT c.id, inq.nombre as Inquilino, i.tipo as Unidad, c.activo FROM contratos c JOIN inquilinos inq ON c.id_inquilino=inq.id JOIN inmuebles i ON c.id_inmueble=i.id", con)
        st.dataframe(df_c, use_container_width=True, hide_index=True)
        if not df_c.empty:
            idc = st.selectbox("Borrar Contrato", df_c['id'].tolist(), format_func=lambda x: f"ID {x} - {df_c[df_c['id']==x]['Inquilino'].values[0]}")
            if st.button("🗑️ Borrar Contrato"): con.execute("DELETE FROM deudas WHERE id_contrato=?", (idc,)); con.execute("DELETE FROM contratos WHERE id=?", (idc,)); con.commit(); st.rerun()
        con.close()

    with t5: # Procesos
        st.subheader("🚀 Generación Masiva")
        mes_anio = st.text_input("Mes/Año (Ej: Junio 2026)")
        if st.button("Generar Alquileres"):
            con = conectar(); activos = pd.read_sql_query("SELECT id, monto_alquiler FROM contratos WHERE activo=1", con)
            for _, c in activos.iterrows():
                con.execute("INSERT INTO deudas (id_contrato, concepto, mes_anio, monto_debe) VALUES (?, 'Alquiler', ?, ?)", (c['id'], mes_anio, c['monto_alquiler']))
            con.commit(); con.close(); st.success("Generado."); st.rerun()
