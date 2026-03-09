import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
import hashlib

st.set_page_config(page_title="Taller SaaS Elite", layout="wide")

# --- FUNCIONES DE SEGURIDAD ---
def generar_hash(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

def conectar_db():
    conn = sqlite3.connect('taller_saas.db', check_same_thread=False)
    cursor = conn.cursor()
    # Tabla de Usuarios
    cursor.execute('CREATE TABLE IF NOT EXISTS usuarios (user TEXT PRIMARY KEY, password TEXT, nombre_taller TEXT)')
    # Tabla de Inventario vinculada al usuario
    cursor.execute('CREATE TABLE IF NOT EXISTS inventario (id INTEGER PRIMARY KEY AUTOINCREMENT, usuario TEXT, repuesto TEXT, stock INTEGER, precio_venta REAL)')
    conn.commit()
    return conn

conn = conectar_db()
cursor = conn.cursor()

# --- SESIÓN DE USUARIO ---
if 'autenticado' not in st.session_state:
    st.session_state.autenticado = False
    st.session_state.usuario = ""
    st.session_state.taller = ""

# --- PANTALLA DE LOGIN / REGISTRO ---
if not st.session_state.autenticado:
    st.title("🚀 Bienvenido a Taller SaaS")
    tab_login, tab_reg = st.tabs(["Iniciar Sesión", "Registrar mi Taller"])
    
    with tab_reg:
        new_user = st.text_input("Usuario (Email)", key="reg_u")
        new_pass = st.text_input("Contraseña", type="password", key="reg_p")
        new_taller = st.text_input("Nombre de tu Taller", key="reg_t")
        if st.button("Crear Cuenta"):
            try:
                cursor.execute("INSERT INTO usuarios VALUES (?, ?, ?)", (new_user, generar_hash(new_pass), new_taller))
                conn.commit()
                st.success("¡Cuenta creada! Ya puedes iniciar sesión.")
            except:
                st.error("El usuario ya existe.")

    with tab_login:
        user = st.text_input("Usuario")
        password = st.text_input("Contraseña", type="password")
        if st.button("Entrar"):
            res = cursor.execute("SELECT password, nombre_taller FROM usuarios WHERE user=?", (user,)).fetchone()
            if res and res[0] == generar_hash(password):
                st.session_state.autenticado = True
                st.session_state.usuario = user
                st.session_state.taller = res[1]
                st.rerun()
            else:
                st.error("Usuario o contraseña incorrectos")
    st.stop()

# --- INTERFAZ DEL TALLER (Solo si está logueado) ---
st.sidebar.title(f"👨‍🔧 {st.session_state.taller}")
if st.sidebar.button("Cerrar Sesión"):
    st.session_state.autenticado = False
    st.rerun()

# Filtrar datos por el usuario actual
user_actual = st.session_state.usuario

t1, t2 = st.tabs(["📄 PRESUPUESTO", "📦 MI STOCK"])

with t1:
    st.subheader(f"Presupuesto para: {st.session_state.taller}")
    # (Aquí iría la misma lógica de presupuesto que ya teníamos, pero filtrando por user_actual)
    st.info("Listo para operar. Carga tu stock en la pestaña de al lado.")

with t2:
    st.header("Gestión de Inventario Personal")
    with st.form("add_inv"):
        c1, c2, c3 = st.columns(3)
        n = c1.text_input("Repuesto")
        s = c2.number_input("Stock", min_value=0)
        p = c3.number_input("Precio", min_value=0.0)
        if st.form_submit_button("Guardar"):
            cursor.execute("INSERT INTO inventario (usuario, repuesto, stock, precio_venta) VALUES (?, ?, ?, ?)", (user_actual, n, s, p))
            conn.commit()
            st.rerun()
    
    # Mostrar solo el stock de este usuario
    df = pd.read_sql_query(f"SELECT repuesto, stock, precio_venta FROM inventario WHERE usuario='{user_actual}'", conn)
    st.dataframe(df, use_container_width=True, hide_index=True)
