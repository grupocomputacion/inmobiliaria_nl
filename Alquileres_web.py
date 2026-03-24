import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, date, timedelta
import io
import urllib.parse

# --- 1. CONFIGURACIÓN DE NAVEGACIÓN Y ESTILO ---
st.set_page_config(
    page_title="Inmobiliaria Pro Cloud", 
    layout="wide", 
    initial_sidebar_state="expanded"
)

# --- 2. FUNCIONES DE APOYO (EL MOTOR DEL SISTEMA) ---
def conectar():
    """Conexión segura a SQLite compatible con hilos de Streamlit"""
    return sqlite3.connect('datos_alquileres.db', check_same_thread=False)

def fmt_moneda(valor):
    """Formatea importes: $ 1.250.000 (sin decimales, con punto de miles)"""
    try:
        # Forzamos float y luego int para limpiar cualquier residuo de la DB
        return f"$ {int(float(valor)):,}".replace(",", ".")
    except:
        return "$ 0"

def crear_link_whatsapp(tel, mensaje):
    """Codifica el mensaje para que funcione como link directo a la App"""
    texto = urllib.parse.quote(mensaje)
    return f"https://api.whatsapp.com/send?phone={tel}&text={texto}"

# --- 3. INICIALIZACIÓN Y AUTO-MIGRACIÓN DE DB ---
def init_db():
    conn = conectar()
    c = conn.cursor()
    
    # Creamos las tablas base si no existen (Basado en tu original)
    c.execute('''CREATE TABLE IF NOT EXISTS bloques (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT UNIQUE)''')
    c.execute('''CREATE TABLE IF NOT EXISTS inmuebles (id INTEGER PRIMARY KEY AUTOINCREMENT, id_bloque INTEGER, tipo TEXT, precio_alquiler REAL, costo_contrato REAL, deposito_base REAL, estado TEXT DEFAULT 'Libre')''')
    c.execute('''CREATE TABLE IF NOT EXISTS inquilinos (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT, celular TEXT, procedencia TEXT, grupo TEXT, em_nombre TEXT, em_tel TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS contratos (id INTEGER PRIMARY KEY AUTOINCREMENT, id_inmueble INTEGER, id_inquilino INTEGER, fecha_inicio DATE, meses INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS deudas (id INTEGER PRIMARY KEY AUTOINCREMENT, id_contrato INTEGER, concepto TEXT, mes_anio TEXT, monto_debe REAL, monto_pago REAL DEFAULT 0, pagado INTEGER DEFAULT 0, fecha_cobro DATE)''')

    # MIGRACIÓN: Agregamos columnas predictivas y financieras si no existen
    # Esto evita el DatabaseError al ejecutar el sistema por primera vez
    columnas_contratos = [
        ("fecha_fin", "DATE"), 
        ("activo", "INTEGER DEFAULT 1"),
        ("monto_alquiler", "REAL DEFAULT 0"), 
        ("monto_contrato", "REAL DEFAULT 0"),
        ("monto_deposito", "REAL DEFAULT 0")
    ]
    for col, tipo in columnas_contratos:
        try:
            c.execute(f"ALTER TABLE contratos ADD COLUMN {col} {tipo}")
        except sqlite3.OperationalError:
            pass # La columna ya existe, no hacemos nada
            
    conn.commit()
    conn.close()

# Ejecutamos la inicialización al cargar el script
init_db()
