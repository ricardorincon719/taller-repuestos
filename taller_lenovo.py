import streamlit as st
import pandas as pd
import psycopg2
from datetime import datetime
import hashlib
import streamlit.components.v1 as components

st.set_page_config(page_title="Taller SaaS Pro", layout="wide")

# --- CONEXIÓN POR URI (MÁXIMA ESTABILIDAD) ---
def conectar_db():
    try:
        # Conecta usando la URI de los secrets (Puerto 6543)
        return psycopg2.connect(st.secrets["postgres"]["uri"], connect_timeout=20)
    except Exception as e:
        st.error(f"Error de conexión: {e}")
        return None

conn = conectar_db()
if conn:
    cursor = conn.cursor()
    # Tablas con sintaxis Postgres
    cursor.execute('CREATE TABLE IF NOT EXISTS usuarios (user_id TEXT PRIMARY KEY, password TEXT, taller TEXT, direccion TEXT, tel TEXT, cuit TEXT)')
    cursor.execute('CREATE TABLE IF NOT EXISTS inventario (id SERIAL PRIMARY KEY, usuario TEXT, sku TEXT, repuesto TEXT, stock INTEGER, precio REAL)')
    cursor.execute('CREATE TABLE IF NOT EXISTS movimientos (id SERIAL PRIMARY KEY, usuario TEXT, tipo TEXT, categoria TEXT, descripcion TEXT, monto REAL, fecha DATE)')
    conn.commit()
else:
    st.stop()

def generar_hash(p): return hashlib.sha256(p.encode()).hexdigest()

if 'autenticado' not in st.session_state:
    st.session_state.update({'autenticado': False, 'user': '', 'datos': {}, 'carrito': []})

# --- LOGIN / REGISTRO ---
if not st.session_state.autenticado:
    st.title("🚀 Gestión de Talleres - SaaS")
    t1, t2 = st.tabs(["🔐 Ingresar", "📝 Registrar"])
    with t2:
        with st.form("reg"):
            u, p = st.text_input("Email"), st.text_input("Pass", type="password")
            nom, dir_t, tel, cui = st.text_input("Taller"), st.text_input("Dir"), st.text_input("Tel"), st.text_input("CUIT")
            if st.form_submit_button("Crear mi cuenta"):
                try:
                    cursor.execute("INSERT INTO usuarios VALUES (%s,%s,%s,%s,%s,%s)", (u, generar_hash(p), nom, dir_t, tel, cui))
                    conn.commit(); st.success("¡Registrado!")
                except: st.error("Error: Usuario duplicado")
    with t1:
        u_l = st.text_input("Email")
        p_l = st.text_input("Contraseña", type="password", key="login_pass")
        if st.button("Entrar"):
            cursor.execute("SELECT password, taller, direccion, tel, cuit FROM usuarios WHERE user_id=%s", (u_l,))
            r = cursor.fetchone()
            if r and r[0] == generar_hash(p_l):
                st.session_state.update({'autenticado': True, 'user': u_l, 'datos': {"t": r[1], "d": r[2], "te": r[3], "c": r[4]}})
                st.rerun()
            else: st.error("Datos incorrectos")
    st.stop()

# --- APP ---
info = st.session_state.datos
st.sidebar.title(f"👨‍🔧 {info.get('t')}")
if st.sidebar.button("Cerrar Sesión"):
    st.session_state.autenticado = False; st.rerun()

# CSS IMPRESIÓN
st.markdown("<style>@media print { .no-print, button, .stSidebar, header, [data-testid='stHeader'], [data-testid='stExpander'], .stForm, .stTabs [data-baseweb='tab-list'] { display: none !important; } .print-header { text-align: center; border-bottom: 2px solid black; } }</style>", unsafe_allow_html=True)

tab1, tab2 = st.tabs(["📄 PRESUPUESTO", "📦 INVENTARIO"])

with tab1:
    st.markdown(f"<div style='text-align:center;'><h1>{info.get('t','').upper()}</h1><p>{info.get('d')} | Tel: {info.get('te')}</p></div>", unsafe_allow_html=True)
    cli = st.text_input("👤 Cliente")
    with st.expander("➕ Cargar ítem"):
        cursor.execute("SELECT sku, repuesto, precio FROM inventario WHERE usuario=%s", (st.session_state.user,))
        items = cursor.fetchall()
        opc = {f"{r[0]} | {r[1]}": (r[0], r[2]) for r in items}
        sel = st.selectbox("Stock", ["---"] + list(opc.keys()))
        can = st.number_input("Cant", min_value=1, value=1)
        pre_u = st.number_input("Precio $", value=float(opc.get(sel, (0, 0.0))[1]))
        if st.button("Añadir"):
            if sel != "---":
                st.session_state.carrito.append({"item": sel, "sku": opc[sel][0], "cant": can, "pre": pre_u, "sub": can*pre_u})
                st.rerun()
    if st.session_state.carrito:
        st.table(pd.DataFrame(st.session_state.carrito))
        if st.button("🖨️ IMPRIMIR"): components.html("<script>window.parent.print();</script>", height=0)

with tab2:
    with st.form("inv"):
        c1, c2, c3, c4 = st.columns(4)
        f_s, f_n, f_c, f_p = c1.text_input("SKU"), c2.text_input("Nombre"), c3.number_input("Cant", min_value=0), c4.number_input("Precio", min_value=0.0)
        if st.form_submit_button("Guardar"):
            cursor.execute("SELECT stock FROM inventario WHERE usuario=%s AND sku=%s", (st.session_state.user, f_s))
            if cursor.fetchone(): cursor.execute("UPDATE inventario SET stock=stock+%s, precio=%s WHERE usuario=%s AND sku=%s", (f_c, f_p, st.session_state.user, f_s))
            else: cursor.execute("INSERT INTO inventario (usuario, sku, repuesto, stock, precio) VALUES (%s,%s,%s,%s,%s)", (st.session_state.user, f_s, f_n, f_c, f_p))
            conn.commit(); st.rerun()
    cursor.execute("SELECT sku, repuesto, stock, precio FROM inventario WHERE usuario=%s", (st.session_state.user,))
    st.dataframe(pd.DataFrame(cursor.fetchall(), columns=['SKU', 'Repuesto', 'Stock', 'Precio']), use_container_width=True, hide_index=True)
