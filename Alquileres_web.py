import streamlit as st
import sqlite3
import pandas as pd

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Inmobiliaria - Gestión Cloud", layout="wide")

def conectar():
    # check_same_thread=False es vital para aplicaciones web
    return sqlite3.connect('gestion_inmobiliaria.db', check_same_thread=False)

def init_db():
    conn = conectar()
    c = conn.cursor()
    # Tabla de Propiedades
    c.execute('''CREATE TABLE IF NOT EXISTS propiedades (
        id INTEGER PRIMARY KEY AUTOINCREMENT, 
        direccion TEXT, 
        tipo TEXT, 
        ambientes INTEGER, 
        precio REAL, 
        propietario TEXT, 
        telefono_prop TEXT, 
        estado TEXT DEFAULT 'DISPONIBLE',
        notas TEXT)''')
    conn.commit()
    conn.close()

init_db()

# --- INTERFAZ ---
st.title("🏠 Sistema Inmobiliario - Panel de Control")

menu = st.sidebar.radio("MENÚ", ["Listado y Filtros", "Registrar Propiedad", "Carga Masiva (Excel)"])

if menu == "Registrar Propiedad":
    st.subheader("🆕 Alta de Inmueble")
    with st.form("alta_prop"):
        col1, col2 = st.columns(2)
        dir = col1.text_input("Dirección Exacta")
        tipo = col2.selectbox("Tipo de Propiedad", ["Casa", "Departamento", "Local", "Terreno", "Cochera"])
        amb = col1.number_input("Ambientes", min_value=1, step=1)
        precio = col2.number_input("Precio (USD/ARS)", min_value=0.0)
        prop = col1.text_input("Nombre del Propietario")
        tel = col2.text_input("Teléfono de Contacto")
        notas = st.text_area("Notas adicionales (Servicios, expensas, etc.)")
        
        if st.form_submit_button("Guardar en la Nube"):
            if dir and prop:
                conn = conectar()
                conn.execute("""INSERT INTO propiedades (direccion, tipo, ambientes, precio, propietario, telefono_prop, notas) 
                             VALUES (?,?,?,?,?,?,?)""", (dir, tipo, amb, precio, prop, tel, notas))
                conn.commit()
                st.success(f"Propiedad en {dir} registrada correctamente.")
            else:
                st.error("Dirección y Propietario son campos obligatorios.")

elif menu == "Listado y Filtros":
    st.subheader("🔍 Buscador de Propiedades")
    
    # Filtros rápidos
    c1, c2, c3 = st.columns(3)
    f_tipo = c1.multiselect("Tipo", ["Casa", "Departamento", "Local", "Terreno"], default=[])
    f_estado = c2.selectbox("Estado", ["TODOS", "DISPONIBLE", "ALQUILADA", "VENDIDA"])
    f_busqueda = c3.text_input("Buscar por dirección o dueño")

    conn = conectar()
    query = "SELECT * FROM propiedades WHERE 1=1"
    params = []
    
    if f_tipo:
        query += f" AND tipo IN ({','.join(['?']*len(f_tipo))})"
        params.extend(f_tipo)
    if f_estado != "TODOS":
        query += " AND estado = ?"; params.append(f_estado)
    if f_busqueda:
        query += " AND (direccion LIKE ? OR propietario LIKE ?)"
        params.extend([f"%{f_busqueda}%", f"%{f_busqueda}%"])

    df = pd.read_sql_query(query, conn, params=params)
    
    # Vista de tabla
    st.dataframe(df, use_container_width=True)

    # Gestión de Propiedad seleccionada
    if not df.empty:
        prop_id = st.selectbox("Seleccione ID para Editar/Cambiar Estado", df['id'].tolist())
        if prop_id:
            with st.expander("📝 Gestionar Ficha Seleccionada"):
                # Traer datos actuales para el formulario de edición
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM propiedades WHERE id=?", (prop_id,))
                d = cursor.fetchone()
                
                new_estado = st.selectbox("Actualizar Estado", ["DISPONIBLE", "ALQUILADA", "VENDIDA", "RESERVADA"], 
                                          index=["DISPONIBLE", "ALQUILADA", "VENDIDA", "RESERVADA"].index(d[7]) if d[7] in ["DISPONIBLE", "ALQUILADA", "VENDIDA", "RESERVADA"] else 0)
                new_precio = st.number_input("Actualizar Precio", value=float(d[4]))
                
                if st.button("Actualizar Propiedad"):
                    conn.execute("UPDATE propiedades SET estado=?, precio=? WHERE id=?", (new_estado, new_precio, prop_id))
                    conn.commit()
                    st.success("Cambios impactados en la base de datos.")
                    st.rerun()

elif menu == "Importar Excel":
    st.subheader("📥 Migración de Cartera")
    archivo = st.file_uploader("Suba su Excel de propiedades", type=["xlsx"])
    if archivo:
        df_migracion = pd.read_excel(archivo)
        st.write("Vista previa del archivo:")
        st.dataframe(df_migracion.head())
        if st.button("Iniciar Carga Masiva"):
            # Aquí iría la lógica de insert masivo similar a la de alumnos
            st.warning("Función de ingesta en proceso...")
