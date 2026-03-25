import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, date, timedelta
import os

# 1. CONFIGURACIÓN ESTRUCTURAL
st.set_page_config(page_title="NL Propiedades", layout="wide")

# 2. CONEXIÓN DIRECTA
conn = sqlite3.connect('datos_alquileres.db', check_same_thread=False)
cursor = conn.cursor()

# 3. ASEGURAR TABLAS (EJECUCIÓN DIRECTA)
cursor.execute("CREATE TABLE IF NOT EXISTS bloques (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT UNIQUE)")
cursor.execute("CREATE TABLE IF NOT EXISTS inmuebles (id INTEGER PRIMARY KEY AUTOINCREMENT, id_bloque INTEGER, tipo TEXT, precio_alquiler INTEGER, costo_contrato INTEGER, deposito_base INTEGER)")
cursor.execute("CREATE TABLE IF NOT EXISTS inquilinos (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT, celular TEXT, dni TEXT, procedencia TEXT)")
cursor.execute("CREATE TABLE IF NOT EXISTS contratos (id INTEGER PRIMARY KEY AUTOINCREMENT, id_inmueble INTEGER, id_inquilino INTEGER, fecha_inicio DATE, fecha_fin DATE, meses INTEGER, activo INTEGER DEFAULT 1, monto_alquiler INTEGER, monto_contrato INTEGER, monto_deposito INTEGER)")
cursor.execute("CREATE TABLE IF NOT EXISTS deudas (id INTEGER PRIMARY KEY AUTOINCREMENT, id_contrato INTEGER, concepto TEXT, mes_anio TEXT, monto_debe INTEGER, monto_pago INTEGER DEFAULT 0, pagado INTEGER DEFAULT 0, fecha_cobro DATE)")
conn.commit()

# 4. MENÚ LATERAL CON VALORES NUMÉRICOS
with st.sidebar:
    st.title("NL PROPIEDADES")
    # Usamos un diccionario para que el ID sea un número, no un texto propenso a errores
    opciones = {
        1: "🏠 1. Inventario",
        2: "📝 2. Nuevo Contrato",
        3: "💰 3. Cobranzas",
        4: "🚨 4. Morosos",
        5: "📊 5. Caja",
        6: "⚙️ 6. Maestros"
    }
    seleccion = st.radio("NAVEGACIÓN:", list(opciones.keys()), format_func=lambda x: opciones[x])
    
    st.write("---")
    if st.button("🚨 FORMATEAR BASE DE DATOS"):
        conn.close()
        if os.path.exists('datos_alquileres.db'):
            os.remove('datos_alquileres.db')
        st.rerun()

# --- UTILIDADES ---
def cl(t): return int(str(t).replace('$', '').replace('.', '').replace(',', '').strip() or 0)

# ==========================================
# SECCIÓN 1: INVENTARIO
# ==========================================
if seleccion == 1:
    st.header("🏠 1. Inventario")
    df = pd.read_sql_query("""
        SELECT b.nombre as Bloque, i.tipo as Unidad, i.precio_alquiler, MAX(c.activo) as ocupado 
        FROM inmuebles i 
        JOIN bloques b ON i.id_bloque = b.id 
        LEFT JOIN contratos c ON i.id = c.id_inmueble AND c.activo = 1 
        GROUP BY i.id
    """, conn)
    if not df.empty:
        df['Estado'] = df['ocupado'].apply(lambda x: "🔴 OCUPADO" if x == 1 else "🟢 LIBRE")
        st.dataframe(df, use_container_width=True)
    else:
        st.info("No hay unidades. Cargue datos en la Sección 6.")

# ==========================================
# SECCIÓN 2: NUEVO CONTRATO
# ==========================================
if seleccion == 2:
    st.header("📝 2. Nuevo Contrato")
    unidades = pd.read_sql_query("SELECT i.id, b.nombre || ' - ' || i.tipo as ref, i.precio_alquiler, i.costo_contrato, i.deposito_base FROM inmuebles i JOIN bloques b ON i.id_bloque=b.id", conn)
    inquilinos = pd.read_sql_query("SELECT id, nombre FROM inquilinos", conn)
    
    if not unidades.empty and not inquilinos.empty:
        with st.form("f_nuevo_contrato"):
            u_id = st.selectbox("Unidad", unidades['id'].tolist(), format_func=lambda x: unidades[unidades['id']==x]['ref'].values[0])
            i_id = st.selectbox("Inquilino", inquilinos['id'].tolist(), format_func=lambda x: inquilinos[inquilinos['id']==x]['nombre'].values[0])
            f_ini = st.date_input("Fecha Inicio", datetime.now())
            meses = st.number_input("Meses", 1, 60, 6)
            
            row = unidades[unidades['id']==u_id].iloc[0]
            m1 = st.text_input("Alquiler Mensual", value=str(row['precio_alquiler']))
            m2 = st.text_input("Costo Contrato", value=str(row['costo_contrato']))
            m3 = st.text_input("Depósito", value=str(row['deposito_base']))
            
            if st.form_submit_button("GRABAR"):
                f_fin = f_ini + timedelta(days=meses*30)
                cursor.execute("INSERT INTO contratos (id_inmueble, id_inquilino, fecha_inicio, fecha_fin, meses, monto_alquiler, monto_contrato, monto_deposito) VALUES (?,?,?,?,?,?,?,?)", (u_id, i_id, f_ini, f_fin, meses, cl(m1), cl(m2), cl(m3)))
                cid = cursor.lastrowid
                m_txt = f_ini.strftime("%m/%Y")
                cursor.executemany("INSERT INTO deudas (id_contrato, concepto, mes_anio, monto_debe) VALUES (?,?,?,?)", [
                    (cid, "Contrato", m_txt, cl(m2)),
                    (cid, "Depósito", m_txt, cl(m3)),
                    (cid, "Mes 1", m_txt, cl(m1))
                ])
                conn.commit()
                st.success("Contrato grabado.")
                st.rerun()
    else:
        st.warning("Cargue Inquilinos y Unidades primero en la Sección 6.")

# ==========================================
# SECCIÓN 3: COBRANZAS
# ==========================================
if seleccion == 3:
    st.header("💰 3. Cobranzas")
    deudas = pd.read_sql_query("""
        SELECT d.id, inq.nombre, i.tipo, d.concepto, d.mes_anio, d.monto_debe, d.monto_pago 
        FROM deudas d 
        JOIN contratos c ON d.id_contrato=c.id 
        JOIN inmuebles i ON c.id_inmueble=i.id 
        JOIN inquilinos inq ON c.id_inquilino=inq.id 
        WHERE d.pagado = 0
    """, conn)
    
    if not deudas.empty:
        for _, r in deudas.iterrows():
            with st.expander(f"{r['nombre']} - {r['tipo']} ({r['concepto']})"):
                cobro = st.text_input("Monto a cobrar", value=str(r['monto_debe'] - r['monto_pago']), key=f"c_{r['id']}")
                if st.button("Confirmar Pago", key=f"b_{r['id']}"):
                    nuevo_p = r['monto_pago'] + cl(cobro)
                    cursor.execute("UPDATE deudas SET monto_pago=?, pagado=?, fecha_cobro=? WHERE id=?", 
                                   (nuevo_p, 1 if nuevo_p >= r['monto_debe'] else 0, datetime.now(), r['id']))
                    conn.commit()
                    st.rerun()
    else:
        st.info("No hay cobros pendientes.")

# ==========================================
# SECCIÓN 4: MOROSOS
# ==========================================
if seleccion == 4:
    st.header("🚨 4. Morosos")
    df_morosos = pd.read_sql_query("""
        SELECT inq.nombre as Inquilino, i.tipo as Unidad, d.concepto as Item, (d.monto_debe - d.monto_pago) as Saldo 
        FROM deudas d 
        JOIN contratos c ON d.id_contrato=c.id 
        JOIN inmuebles i ON c.id_inmueble=i.id 
        JOIN inquilinos inq ON c.id_inquilino=inq.id 
        WHERE d.pagado = 0
    """, conn)
    if not df_morosos.empty:
        st.table(df_morosos)
    else:
        st.success("No hay morosos registrados.")

# ==========================================
# SECCIÓN 5: CAJA
# ==========================================
if seleccion == 5:
    st.header("📊 5. Caja")
    df_caja = pd.read_sql_query("""
        SELECT fecha_cobro as Fecha, concepto as Detalle, monto_pago as Importe 
        FROM deudas 
        WHERE pagado = 1
    """, conn)
    if not df_caja.empty:
        st.dataframe(df_caja, use_container_width=True)
        st.write(f"**Total en Caja: $ {df_caja['Importe'].sum():,}**")
    else:
        st.info("Aún no hay ingresos registrados.")

# ==========================================
# SECCIÓN 6: MAESTROS
# ==========================================
if seleccion == 6:
    st.header("⚙️ 6. Maestros")
    t1, t2, t3, t4 = st.tabs(["Inquilinos", "Bloques", "Unidades", "Contratos"])
    
    with t1:
        with st.form("f_inq"):
            n = st.text_input("Nombre Completo"); d = st.text_input("DNI"); w = st.text_input("WhatsApp")
            if st.form_submit_button("Guardar"):
                cursor.execute("INSERT INTO inquilinos (nombre, dni, celular) VALUES (?,?,?)", (n, d, w))
                conn.commit(); st.rerun()
        st.dataframe(pd.read_sql_query("SELECT id, nombre, dni FROM inquilinos", conn), use_container_width=True)
        
    with t2:
        nb = st.text_input("Nombre del Bloque")
        if st.button("Guardar Bloque"):
            cursor.execute("INSERT INTO bloques (nombre) VALUES (?)", (nb,))
            conn.commit(); st.rerun()
        st.table(pd.read_sql_query("SELECT * FROM bloques", conn))
        
    with t3:
        bls = pd.read_sql_query("SELECT * FROM bloques", conn)
        if not bls.empty:
            with st.form("f_uni"):
                b_id = st.selectbox("Bloque", bls['id'].tolist(), format_func=lambda x: bls[bls['id']==x]['nombre'].values[0])
                ut = st.text_input("Nombre Unidad")
                p1 = st.text_input("Alquiler"); p2 = st.text_input("Contrato"); p3 = st.text_input("Depósito")
                if st.form_submit_button("Guardar Unidad"):
                    cursor.execute("INSERT INTO inmuebles (id_bloque, tipo, precio_alquiler, costo_contrato, deposito_base) VALUES (?,?,?,?,?)", (b_id, ut, cl(p1), cl(p2), cl(p3)))
                    conn.commit(); st.rerun()
        st.dataframe(pd.read_sql_query("SELECT i.id, b.nombre as Bloque, i.tipo as Unidad FROM inmuebles i JOIN bloques b ON i.id_bloque=b.id", conn))

    with t4:
        df_con = pd.read_sql_query("""
            SELECT c.id, inq.nombre as Inquilino, i.tipo as Unidad, c.activo 
            FROM contratos c 
            JOIN inquilinos inq ON c.id_inquilino = inq.id 
            JOIN inmuebles i ON c.id_inmueble = i.id
        """, conn)
        st.dataframe(df_con, use_container_width=True)
        idc = st.number_input("ID Contrato a borrar", step=1, value=0)
        if st.button("Eliminar Contrato"):
            cursor.execute(f"DELETE FROM deudas WHERE id_contrato={idc}")
            cursor.execute(f"DELETE FROM contratos WHERE id={idc}")
            conn.commit(); st.rerun()

conn.close()
