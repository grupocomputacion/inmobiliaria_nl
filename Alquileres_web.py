import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, date, timedelta
import os

# 1. CONFIGURACIÓN ESTRUCTURAL
st.set_page_config(page_title="NL PROPIEDADES - GESTIÓN", layout="wide")

# 2. BASE DE DATOS (CONEXIÓN Y TABLAS)
def conectar():
    return sqlite3.connect('datos_alquileres.db', check_same_thread=False)

conn = conectar()
cur = conn.cursor()

# Esquema de datos garantizado
cur.executescript('''
    CREATE TABLE IF NOT EXISTS bloques (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT UNIQUE);
    CREATE TABLE IF NOT EXISTS inmuebles (id INTEGER PRIMARY KEY AUTOINCREMENT, id_bloque INTEGER, tipo TEXT, precio_alquiler INTEGER, costo_contrato INTEGER, deposito_base INTEGER);
    CREATE TABLE IF NOT EXISTS inquilinos (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT, dni TEXT, celular TEXT);
    CREATE TABLE IF NOT EXISTS contratos (id INTEGER PRIMARY KEY AUTOINCREMENT, id_inmueble INTEGER, id_inquilino INTEGER, fecha_inicio DATE, fecha_fin DATE, meses INTEGER, activo INTEGER DEFAULT 1, monto_alquiler INTEGER, monto_contrato INTEGER, monto_deposito INTEGER);
    CREATE TABLE IF NOT EXISTS deudas (id INTEGER PRIMARY KEY AUTOINCREMENT, id_contrato INTEGER, concepto TEXT, mes_anio TEXT, monto_debe INTEGER, monto_pago INTEGER DEFAULT 0, pagado INTEGER DEFAULT 0, fecha_cobro DATE);
''')
conn.commit()

# --- UTILIDADES ---
def cl(t): return int(str(t).replace('$', '').replace('.', '').replace(',', '').strip() or 0)
def f_m(v): return f"$ {int(v or 0):,}".replace(",", ".")

# 3. NAVEGACIÓN POR ÍNDICE (EVITA ERRORES DE TEXTO)
opciones = ["1. Inventario", "2. Nuevo Contrato", "3. Cobranzas", "4. Morosos", "5. Caja", "6. Maestros"]

with st.sidebar:
    st.title("NL PROPIEDADES")
    st.write("---")
    # Usamos el índice de la lista para la lógica, no el texto
    seleccion = st.selectbox("SELECCIONE FUNCIÓN:", range(len(opciones)), format_func=lambda x: opciones[x])
    st.write("---")
    if st.button("🚨 FORMATEAR SISTEMA"):
        if os.path.exists('datos_alquileres.db'):
            conn.close()
            os.remove('datos_alquileres.db')
            st.rerun()

# 4. RENDERIZADO DE SECCIONES (LÓGICA INDEPENDIENTE)

# --- SECCIÓN 1: INVENTARIO ---
if seleccion == 0:
    st.header("🏠 1. Inventario y Estado")
    try:
        df = pd.read_sql_query("SELECT b.nombre as Bloque, i.tipo as Unidad, i.precio_alquiler as Alquiler FROM inmuebles i JOIN bloques b ON i.id_bloque = b.id", conn)
        if not df.empty:
            st.dataframe(df, use_container_width=True)
        else:
            st.info("No hay datos cargados. Vaya a la sección 6 (Maestros).")
    except Exception as e:
        st.error(f"Error técnico en Inventario: {e}")

# --- SECCIÓN 2: NUEVO CONTRATO ---
if seleccion == 1:
    st.header("📝 2. Generar Nuevo Contrato")
    try:
        u_df = pd.read_sql_query("SELECT i.id, b.nombre || ' - ' || i.tipo as ref, i.precio_alquiler, i.costo_contrato, i.deposito_base FROM inmuebles i JOIN bloques b ON i.id_bloque=b.id", conn)
        i_df = pd.read_sql_query("SELECT id, nombre FROM inquilinos", conn)
        if not u_df.empty and not i_df.empty:
            with st.form("f_contrato"):
                c1, c2 = st.columns(2)
                u_id = c1.selectbox("Unidad", u_df['id'].tolist(), format_func=lambda x: u_df[u_df['id']==x]['ref'].values[0])
                i_id = c2.selectbox("Inquilino", i_df['id'].tolist(), format_func=lambda x: i_df[i_df['id']==x]['nombre'].values[0])
                f_ini = c1.date_input("Fecha Inicio", date.today())
                meses = c2.number_input("Meses de Contrato", 1, 60, 6)
                
                row = u_df[u_df['id']==u_id].iloc[0]
                m1 = st.text_input("Monto Alquiler", value=str(row['precio_alquiler']))
                m2 = st.text_input("Monto Contrato", value=str(row['costo_contrato']))
                m3 = st.text_input("Monto Depósito", value=str(row['deposito_base']))
                
                if st.form_submit_button("GRABAR Y GENERAR DEUDAS"):
                    f_fin = f_ini + timedelta(days=meses*30)
                    cur.execute("INSERT INTO contratos (id_inmueble, id_inquilino, fecha_inicio, fecha_fin, meses, monto_alquiler, monto_contrato, monto_deposito) VALUES (?,?,?,?,?,?,?,?)", (u_id, i_id, f_ini, f_fin, meses, cl(m1), cl(m2), cl(m3)))
                    cid = cur.lastrowid
                    m_txt = f_ini.strftime("%m/%y")
                    cur.executemany("INSERT INTO deudas (id_contrato, concepto, mes_anio, monto_debe) VALUES (?,?,?,?)", [
                        (cid, "Costo Contrato", m_txt, cl(m2)),
                        (cid, "Depósito Garantía", m_txt, cl(m3)),
                        (cid, "Alquiler Mes 1", m_txt, cl(m1))
                    ])
                    conn.commit()
                    st.success("✅ Contrato Guardado correctamente.")
        else:
            st.warning("⚠️ Requiere Inquilinos y Unidades cargadas en Maestros.")
    except Exception as e:
        st.error(f"Error técnico en Nuevo Contrato: {e}")

# --- SECCIÓN 3: COBRANZAS ---
if seleccion == 2:
    st.header("💰 3. Panel de Cobranzas")
    try:
        deudas = pd.read_sql_query("SELECT d.id, inq.nombre, i.tipo, d.concepto, d.monto_debe, d.monto_pago FROM deudas d JOIN contratos c ON d.id_contrato=c.id JOIN inmuebles i ON c.id_inmueble=i.id JOIN inquilinos inq ON c.id_inquilino=inq.id WHERE d.pagado=0", conn)
        if not deudas.empty:
            for _, r in deudas.iterrows():
                with st.expander(f"{r['nombre']} - {r['tipo']} ({r['concepto']})"):
                    p_monto = st.text_input("Monto a cobrar", value=str(r['monto_debe']-r['monto_pago']), key=f"cobro_{r['id']}")
                    if st.button("Confirmar Pago", key=f"btn_{r['id']}"):
                        cur.execute("UPDATE deudas SET monto_pago=?, pagado=1, fecha_cobro=? WHERE id=?", (cl(p_monto), date.today(), r['id']))
                        conn.commit()
                        st.rerun()
        else:
            st.info("No hay deudas pendientes.")
    except Exception as e:
        st.error(f"Error técnico en Cobranzas: {e}")

# --- SECCIÓN 4: MOROSOS ---
if seleccion == 3:
    st.header("🚨 4. Reporte de Morosos")
    try:
        df_m = pd.read_sql_query("SELECT inq.nombre as Inquilino, i.tipo as Unidad, d.concepto, (d.monto_debe-d.monto_pago) as Saldo FROM deudas d JOIN contratos c ON d.id_contrato=c.id JOIN inmuebles i ON c.id_inmueble=i.id JOIN inquilinos inq ON c.id_inquilino=inq.id WHERE d.pagado=0", conn)
        if not df_m.empty:
            st.table(df_m)
        else:
            st.success("¡Sin morosos! Todo al día.")
    except Exception as e:
        st.error(f"Error técnico en Morosos: {e}")

# --- SECCIÓN 5: CAJA ---
if seleccion == 4:
    st.header("📊 5. Movimientos de Caja")
    try:
        df_c = pd.read_sql_query("SELECT fecha_cobro as Fecha, concepto as Detalle, monto_pago as Importe FROM deudas WHERE pagado=1", conn)
        if not df_c.empty:
            st.metric("Total en Caja", f_m(df_c['Importe'].sum()))
            st.dataframe(df_c, use_container_width=True)
        else:
            st.info("Caja vacía.")
    except Exception as e:
        st.error(f"Error técnico en Caja: {e}")

# --- SECCIÓN 6: MAESTROS ---
if seleccion == 5:
    st.header("⚙️ 6. Maestros y Configuración")
    t1, t2, t3 = st.tabs(["Inquilinos", "Bloques", "Unidades"])
    
    with t1:
        with st.form("form_inq"):
            n = st.text_input("Nombre Completo"); d = st.text_input("DNI / CUIT")
            if st.form_submit_button("Cargar Inquilino"):
                cur.execute("INSERT INTO inquilinos (nombre, dni) VALUES (?,?)", (n, d))
                conn.commit(); st.rerun()
        st.dataframe(pd.read_sql_query("SELECT * FROM inquilinos", conn), use_container_width=True)

    with t2:
        nb = st.text_input("Nombre del Bloque")
        if st.button("Guardar Bloque"):
            cur.execute("INSERT INTO bloques (nombre) VALUES (?)", (nb,))
            conn.commit(); st.rerun()
        st.table(pd.read_sql_query("SELECT * FROM bloques", conn))

    with t3:
        bls = pd.read_sql_query("SELECT * FROM bloques", conn)
        if not bls.empty:
            with st.form("form_uni"):
                bid = st.selectbox("Bloque", bls['id'].tolist(), format_func=lambda x: bls[bls['id']==x]['nombre'].values[0])
                ut = st.text_input("Unidad")
                p1 = st.text_input("Alquiler Sug."); p2 = st.text_input("Contrato Sug."); p3 = st.text_input("Depósito Sug.")
                if st.form_submit_button("Guardar Unidad"):
                    cur.execute("INSERT INTO inmuebles (id_bloque, tipo, precio_alquiler, costo_contrato, deposito_base) VALUES (?,?,?,?,?)", (bid, ut, cl(p1), cl(p2), cl(p3)))
                    conn.commit(); st.rerun()
        st.dataframe(pd.read_sql_query("SELECT i.id, b.nombre as Bloque, i.tipo as Unidad FROM inmuebles i JOIN bloques b ON i.id_bloque=b.id", conn))

conn.close()
