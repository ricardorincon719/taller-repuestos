import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
import hashlib
import streamlit.components.v1 as components

st.set_page_config(page_title="Taller SaaS Pro", layout="wide")

# --- DB & SEGURIDAD ---
def generar_hash(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

def conectar_db():
    # Nueva versión de DB para limpiar residuos
    conn = sqlite3.connect('taller_saas_v4.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('CREATE TABLE IF NOT EXISTS usuarios (user TEXT PRIMARY KEY, password TEXT, taller TEXT, direccion TEXT, tel TEXT, cuit TEXT)')
    cursor.execute('CREATE TABLE IF NOT EXISTS inventario (id INTEGER PRIMARY KEY AUTOINCREMENT, usuario TEXT, repuesto TEXT, stock INTEGER, precio REAL)')
    conn.commit()
    return conn

conn = conectar_db()
cursor = conn.cursor()

# --- INICIALIZACIÓN DEL ESTADO ---
if 'autenticado' not in st.session_state:
    st.session_state.autenticado = False
if 'user' not in st.session_state:
    st.session_state.user = ''
if 'datos' not in st.session_state:
    st.session_state.datos = {}
if 'carrito' not in st.session_state:
    st.session_state.carrito = []

# --- LOGIN / REGISTRO ---
if not st.session_state.autenticado:
    st.title("🛠️ SaaS Gestión de Talleres")
    t_log, t_reg = st.tabs(["Ingresar", "Registrar Nuevo Taller"])
    
    with t_reg:
        with st.form("reg"):
            u = st.text_input("Email / Usuario")
            p = st.text_input("Contraseña", type="password")
            nom = st.text_input("Nombre del Taller")
            dir_t = st.text_input("Dirección")
            tel_t = st.text_input("Teléfono")
            cuit_t = st.text_input("CUIT / RUT")
            if st.form_submit_button("Crear mi cuenta SaaS"):
                try:
                    cursor.execute("INSERT INTO usuarios VALUES (?,?,?,?,?,?)", (u, generar_hash(p), nom, dir_t, tel_t, cuit_t))
                    conn.commit()
                    st.success("¡Registrado! Ya podés iniciar sesión.")
                except: st.error("El usuario ya existe.")

    with t_log:
        u_l = st.text_input("Usuario")
        p_l = st.text_input("Contraseña", type="password")
        if st.button("Entrar"):
            res = cursor.execute("SELECT password, taller, direccion, tel, cuit FROM usuarios WHERE user=?", (u_l,)).fetchone()
            if res and res[0] == generar_hash(p_l):
                st.session_state.autenticado = True
                st.session_state.user = u_l
                st.session_state.datos = {
                    "taller": res[1], 
                    "dir": res[2], 
                    "tel": res[3], 
                    "cuit": res[4]
                }
                st.rerun()
            else: st.error("Error de acceso")
    st.stop()

# --- INTERFAZ POST-LOGIN (BLINDADA) ---
user_actual = st.session_state.user
info = st.session_state.datos

# Usamos .get() para evitar el KeyError
nombre_muestrate = info.get('taller', 'Mi Taller')
direccion_muestrate = info.get('dir', 'S/D')

st.sidebar.title(f"👨‍🔧 {nombre_muestrate}")
st.sidebar.write(f"📍 {direccion_muestrate}")

if st.sidebar.button("Cerrar Sesión"):
    st.session_state.autenticado = False
    st.session_state.user = ''
    st.session_state.datos = {}
    st.rerun()

# CSS IMPRESIÓN
st.markdown("<style>@media print { .no-print, button, .stSidebar, header, [data-testid='stHeader'], [data-testid='stExpander'] { display: none !important; } .print-header { text-align: center; border-bottom: 2px solid black; } }</style>", unsafe_allow_html=True)

tab1, tab2 = st.tabs(["📄 PRESUPUESTO", "📦 INVENTARIO"])

with tab1:
    st.markdown(f"<div class='print-header'><h1>{nombre_muestrate.upper()}</h1><p>{direccion_muestrate} | Tel: {info.get('tel','')} | {info.get('cuit','')}</p></div>", unsafe_allow_html=True)
    cli = st.text_input("👤 Cliente / Vehículo")
    st.write(f"📅 Fecha: {datetime.now().strftime('%d/%m/%Y')}")

    with st.expander("➕ Agregar Ítem", expanded=True):
        c1, c2, c3 = st.columns(3)
        items_db = cursor.execute("SELECT repuesto, precio FROM inventario WHERE usuario=?", (user_actual,)).fetchall()
        opciones_dict = {r[0]: r[1] for r in items_db}
        
        sel = c1.selectbox("Elegir de mi Stock", ["---"] + list(opciones_dict.keys()))
        man = c1.text_input("O Servicio Manual")
        can = c2.number_input("Cantidad", min_value=1, value=1)
        
        precio_u = c3.number_input("Precio Unitario $", min_value=0.0, value=float(opciones_dict.get(sel, 0.0)))
        
        if st.button("Añadir al presupuesto"):
            nom_f = sel if sel != "---" else man
            if nom_f:
                st.session_state.carrito.append({"item": nom_f, "cant": can, "pre": precio_u, "sub": can * precio_u, "es_s": sel != "---"})
                st.rerun()

    if st.session_state.carrito:
        df_p = pd.DataFrame(st.session_state.carrito)
        st.table(df_p[["item", "cant", "pre", "sub"]])
        st.header(f"TOTAL: ${df_p['sub'].sum():,.2f}")
        
        b1, b2, b3 = st.columns(3)
        if b1.button("🖨️ IMPRIMIR"):
            components.html("<script>window.parent.print();</script>", height=0)
        if b2.button("🚀 FINALIZAR Y DESCONTAR", type="primary"):
            for r in st.session_state.carrito:
                if r["es_s"]:
                    cursor.execute("UPDATE inventario SET stock = stock - ? WHERE repuesto = ? AND usuario = ?", (r["cant"], r["item"], user_actual))
            conn.commit()
            st.session_state.carrito = []
            st.success("Venta guardada.")
            st.rerun()
        if b3.button("🗑️ VACIAR"):
            st.session_state.carrito = []
            st.rerun()

with tab2:
    st.header("📦 Mi Almacén")
    with st.form("f_inv"):
        i1, i2, i3 = st.columns(3)
        nom_i = i1.text_input("Nombre Repuesto")
        sto_i = i2.number_input("Stock", min_value=0)
        pre_i = i3.number_input("Precio", min_value=0.0)
        if st.form_submit_button("Guardar"):
            cursor.execute("INSERT OR REPLACE INTO inventario (usuario, repuesto, stock, precio) VALUES (?,?,?,?)", (user_actual, nom_i, sto_i, pre_i))
            conn.commit()
            st.rerun()
    
    df_i = pd.read_sql_query("SELECT repuesto as 'Repuesto', stock as 'Stock', precio as 'Precio' FROM inventario WHERE usuario=?", conn, params=(user_actual,))
    st.dataframe(df_i, use_container_width=True, hide_index=True)
