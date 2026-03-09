import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
import hashlib
import streamlit.components.v1 as components

st.set_page_config(page_title="Taller SaaS Pro", layout="wide")

# --- DB & SEGURIDAD ---
def conectar_db():
    conn = sqlite3.connect('taller_saas_v9.db', check_same_thread=False)
    cursor = conn.cursor()
    # Usuarios e Inventario
    cursor.execute('CREATE TABLE IF NOT EXISTS usuarios (user TEXT PRIMARY KEY, password TEXT, taller TEXT, direccion TEXT, tel TEXT, cuit TEXT)')
    cursor.execute('CREATE TABLE IF NOT EXISTS inventario (id INTEGER PRIMARY KEY AUTOINCREMENT, usuario TEXT, sku TEXT, repuesto TEXT, stock INTEGER, precio REAL)')
    # Tablas Financieras para el SaaS
    cursor.execute('CREATE TABLE IF NOT EXISTS movimientos (id INTEGER PRIMARY KEY AUTOINCREMENT, usuario TEXT, tipo TEXT, categoria TEXT, descripcion TEXT, monto REAL, fecha TEXT)')
    conn.commit()
    return conn

conn = conectar_db()
cursor = conn.cursor()

# --- SESIÓN ---
for k in ['autenticado', 'user', 'datos', 'carrito']:
    if k not in st.session_state: st.session_state[k] = False if k=='autenticado' else ('' if k=='user' else ({} if k=='datos' else []))

# --- LOGIN / REGISTRO ---
if not st.session_state.autenticado:
    st.title("🚀 SaaS Taller - Acceso Profesional")
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

# --- CSS DE IMPRESIÓN (PULIDO TOTAL) ---
st.markdown("""
    <style>
    @media print {
        .no-print, button, .stSidebar, header, [data-testid="stHeader"], [data-testid="stExpander"], .stForm, .stTabs { 
            display: none !important; 
        }
        .print-header { text-align: center; border-bottom: 2px solid black; padding-bottom: 10px; margin-bottom: 20px; }
        .stTable { width: 100% !important; font-size: 12pt; }
    }
    </style>
""", unsafe_allow_html=True)

tab_p, tab_i, tab_f = st.tabs(["📄 PRESUPUESTO", "📦 INVENTARIO", "📊 ADMINISTRACIÓN"])

with tab_p:
    st.markdown(f"<div class='print-header'><h1>{info.get('taller','').upper()}</h1><p>{info.get('dir','')} | Tel: {info.get('tel','')} | {info.get('cuit','')}</p></div>", unsafe_allow_html=True)
    cliente_nom = st.text_input("👤 Cliente / Vehículo", key="cli_p")
    
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
        total_v = df_p['sub'].sum()
        st.header(f"TOTAL: ${total_v:,.2f}")
        
        c_b1, c_b2 = st.columns(2)
        if c_b1.button("🖨️ IMPRIMIR"): components.html("<script>window.parent.print();</script>", height=0)
        if c_b2.button("🚀 FINALIZAR VENTA", type="primary"):
            for r in st.session_state.carrito:
                if r["es_s"]: cursor.execute("UPDATE inventario SET stock = stock - ? WHERE sku = ? AND usuario = ?", (r["cant"], r["sku"], user_act))
            
            # Registrar Ingreso en Movimientos
            cursor.execute("INSERT INTO movimientos (usuario, tipo, categoria, descripcion, monto, fecha) VALUES (?,?,?,?,?,?)", 
                           (user_act, "INGRESO", "VENTA", f"Venta Cliente: {cliente_nom}", total_v, datetime.now().strftime('%Y-%m-%d %H:%M')))
            
            conn.commit(); st.session_state.carrito = []; st.success("✅ Venta y Movimiento Guardado"); st.rerun()

with tab_i:
    st.header("📦 Gestión de Almacén")
    with st.form("ingreso"):
        c1, c2, c3, c4 = st.columns(4)
        f_sku, f_nom, f_sto, f_pre = c1.text_input("SKU"), c2.text_input("Nombre"), c3.number_input("Cant.", min_value=0), c4.number_input("Precio Venta", min_value=0.0)
        b_n, b_s = st.form_submit_button("🆕 NUEVO"), st.form_submit_button("➕ ACTUALIZAR")
        if b_n and f_sku:
            cursor.execute("INSERT INTO inventario (usuario, sku, repuesto, stock, precio) VALUES (?,?,?,?,?)", (user_act, f_sku, f_nom, f_sto, f_pre))
            conn.commit(); st.rerun()
        if b_s and f_sku:
            cursor.execute("UPDATE inventario SET stock=stock+?, precio=? WHERE usuario=? AND sku=?", (f_sto, f_pre, user_act, f_sku))
            conn.commit(); st.rerun()
    st.dataframe(pd.read_sql_query("SELECT sku, repuesto, stock, precio FROM inventario WHERE usuario=?", conn, params=(user_act,)), use_container_width=True, hide_index=True)

with tab_f:
    st.header("📊 Administración y KPI")
    st.info("Carga aquí tus gastos (Proveedores, Sueldos, Alquiler). Las ventas se cargan solas.")
    
    with st.form("gastos"):
        g1, g2, g3 = st.columns(3)
        g_cat = g1.selectbox("Categoría", ["PROVEEDOR", "EMPLEADOS", "ALQUILER", "OTROS"])
        g_desc = g2.text_input("Descripción (Ej: Pago a Repuestos Pepe)")
        g_monto = g3.number_input("Monto $", min_value=0.0)
        if st.form_submit_button("Registrar Gasto"):
            cursor.execute("INSERT INTO movimientos (usuario, tipo, categoria, descripcion, monto, fecha) VALUES (?,?,?,?,?,?)", 
                           (user_act, "EGRESO", g_cat, g_desc, g_monto, datetime.now().strftime('%Y-%m-%d %H:%M')))
            conn.commit(); st.rerun()

    st.markdown("---")
    # KPI Básico
    df_mov = pd.read_sql_query("SELECT * FROM movimientos WHERE usuario=?", conn, params=(user_act,))
    if not df_mov.empty:
        ingresos = df_mov[df_mov['tipo'] == 'INGRESO']['monto'].sum()
        egresos = df_mov[df_mov['tipo'] == 'EGRESO']['monto'].sum()
        balance = ingresos - egresos
        
        k1, k2, k3 = st.columns(3)
        k1.metric("Ingresos Totales", f"${ingresos:,.2f}")
        k2.metric("Egresos Totales", f"${egresos:,.2f}", delta_color="inverse")
        k3.metric("Balance Neto", f"${balance:,.2f}")
        
        st.subheader("Historial de Movimientos")
        st.dataframe(df_mov[["fecha", "tipo", "categoria", "descripcion", "monto"]].sort_values("fecha", ascending=False), use_container_width=True, hide_index=True)
