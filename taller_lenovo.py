import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
import hashlib
import streamlit.components.v1 as components

st.set_page_config(page_title="Taller SaaS Pro", layout="wide")

# --- DB & SEGURIDAD ---
def conectar_db():
    conn = sqlite3.connect('taller_saas_v8.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('CREATE TABLE IF NOT EXISTS usuarios (user TEXT PRIMARY KEY, password TEXT, taller TEXT, direccion TEXT, tel TEXT, cuit TEXT)')
    cursor.execute('CREATE TABLE IF NOT EXISTS inventario (id INTEGER PRIMARY KEY AUTOINCREMENT, usuario TEXT, sku TEXT, repuesto TEXT, stock INTEGER, precio REAL)')
    conn.commit()
    return conn

conn = conectar_db()
cursor = conn.cursor()

# --- SESIÓN ---
for k in ['autenticado', 'user', 'datos', 'carrito']:
    if k not in st.session_state: st.session_state[k] = False if k=='autenticado' else ('' if k=='user' else ({} if k=='datos' else []))

# --- LOGIN / REGISTRO ---
if not st.session_state.autenticado:
    st.title("🚀 SaaS Taller - Acceso")
    t1, t2 = st.tabs(["Ingresar", "Registrar"])
    with t2:
        with st.form("r"):
            u, p = st.text_input("Email"), st.text_input("Contraseña", type="password")
            nom, dir_t, tel, cui = st.text_input("Taller"), st.text_input("Dirección"), st.text_input("Teléfono"), st.text_input("CUIT/RUT")
            if st.form_submit_button("Crear Cuenta"):
                try:
                    cursor.execute("INSERT INTO usuarios VALUES (?,?,?,?,?,?)", (u, hashlib.sha256(p.encode()).hexdigest(), nom, dir_t, tel, cui))
                    conn.commit(); st.success("¡Cuenta creada!")
                except: st.error("Error: El usuario ya existe.")
    with t1:
        u_l, p_l = st.text_input("Email"), st.text_input("Contraseña", type="password", key="login_p")
        if st.button("Entrar al Panel"):
            r = cursor.execute("SELECT password, taller, direccion, tel, cuit FROM usuarios WHERE user=?", (u_l,)).fetchone()
            if r and r[0] == hashlib.sha256(p_l.encode()).hexdigest():
                st.session_state.update({'autenticado':True, 'user':u_l, 'datos':{"taller":r[1],"dir":r[2],"tel":r[3],"cuit":r[4]}})
                st.rerun()
            else: st.error("Credenciales incorrectas.")
    st.stop()

# --- APP ---
user_act = st.session_state.user
info = st.session_state.datos
st.sidebar.title(f"🛠️ {info.get('taller')}")
if st.sidebar.button("Cerrar Sesión"):
    st.session_state.autenticado = False
    st.rerun()

tab_p, tab_i = st.tabs(["📄 PRESUPUESTO", "📦 INVENTARIO SKU"])

with tab_p:
    st.markdown(f"<div style='text-align:center; border-bottom:2px solid black; padding-bottom:10px;'><h1>{info.get('taller','').upper()}</h1><p>{info.get('dir','')} | Tel: {info.get('tel','')} | {info.get('cuit','')}</p></div>", unsafe_allow_html=True)
    cliente_nom = st.text_input("👤 Cliente / Vehículo")
    
    with st.expander("➕ Cargar al Presupuesto", expanded=True):
        items = cursor.execute("SELECT sku, repuesto, precio FROM inventario WHERE usuario=?", (user_act,)).fetchall()
        opc_dict = {f"{r[0]} | {r[1]}": (r[0], r[2]) for r in items}
        sel = st.selectbox("Buscar en Stock", ["---"] + list(opc_dict.keys()))
        man = st.text_input("O Servicio Manual")
        c1, c2 = st.columns(2)
        can = c1.number_input("Cantidad", min_value=1, value=1)
        pre_sug = opc_dict[sel][1] if sel != "---" else 0.0
        pre = c2.number_input("Precio Unitario $", value=float(pre_sug))
        if st.button("Añadir Ítem"):
            nom_item = sel if sel != "---" else man
            sku_val = opc_dict[sel][0] if sel != "---" else None
            if nom_item:
                st.session_state.carrito.append({"item": nom_item, "sku": sku_val, "cant": can, "pre": pre, "sub": can*pre, "es_s": sel != "---"})
                st.rerun()

    if st.session_state.carrito:
        df_p = pd.DataFrame(st.session_state.carrito)
        st.table(df_p[["item", "cant", "pre", "sub"]])
        st.header(f"TOTAL: ${df_p['sub'].sum():,.2f}")
        if st.button("🖨️ IMPRIMIR"): components.html("<script>window.parent.print();</script>", height=0)
        if st.button("🚀 FINALIZAR VENTA", type="primary"):
            for r in st.session_state.carrito:
                if r["es_s"]: cursor.execute("UPDATE inventario SET stock = stock - ? WHERE sku = ? AND usuario = ?", (r["cant"], r["sku"], user_act))
            conn.commit(); st.session_state.carrito = []; st.success("✅ Venta Guardada"); st.rerun()

with tab_i:
    st.header("📦 Gestión de Almacén")
    with st.form("ingreso"):
        c1, c2, c3, c4 = st.columns(4)
        f_sku = c1.text_input("SKU / Código")
        f_nom = c2.text_input("Nombre Repuesto")
        f_sto = c3.number_input("Stock", min_value=0) # Ahora permite 0 para solo actualizar precio
        f_pre = c4.number_input("Precio Venta", min_value=0.0)
        
        b_nuevo = st.form_submit_button("🆕 REGISTRAR NUEVO")
        b_sumar = st.form_submit_button("➕ ACTUALIZAR EXISTENTE")

        if b_nuevo and f_sku and f_nom:
            try:
                cursor.execute("INSERT INTO inventario (usuario, sku, repuesto, stock, precio) VALUES (?,?,?,?,?)", (user_act, f_sku, f_nom, f_sto, f_pre))
                conn.commit(); st.success("Registrado")
            except: st.error("El SKU ya existe")
        
        if b_sumar and f_sku:
            ex = cursor.execute("SELECT stock FROM inventario WHERE usuario=? AND sku=?", (user_act, f_sku)).fetchone()
            if ex:
                # ACÁ ESTÁ EL CAMBIO: Siempre actualiza al precio que pongas en el formulario
                cursor.execute("UPDATE inventario SET stock=stock+?, precio=? WHERE usuario=? AND sku=?", (f_sto, f_pre, user_act, f_sku))
                conn.commit(); st.success(f"Datos actualizados para SKU {f_sku}")
                st.rerun()
            else: st.error("SKU no encontrado")

    st.markdown("---")
    df_inv = pd.read_sql_query("SELECT sku as 'SKU', repuesto as 'Repuesto', stock as 'Cant', precio as 'Precio' FROM inventario WHERE usuario=?", conn, params=(user_act,))
    st.dataframe(df_inv, use_container_width=True, hide_index=True)
