import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
import hashlib
import streamlit.components.v1 as components

st.set_page_config(page_title="Taller SaaS Elite", layout="wide")

# --- DB & SEGURIDAD ---
def conectar_db():
    conn = sqlite3.connect('taller_saas_v11.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('CREATE TABLE IF NOT EXISTS usuarios (user TEXT PRIMARY KEY, password TEXT, taller TEXT, direccion TEXT, tel TEXT, cuit TEXT)')
    cursor.execute('CREATE TABLE IF NOT EXISTS inventario (id INTEGER PRIMARY KEY AUTOINCREMENT, usuario TEXT, sku TEXT, repuesto TEXT, stock INTEGER, precio REAL)')
    cursor.execute('CREATE TABLE IF NOT EXISTS movimientos (id INTEGER PRIMARY KEY AUTOINCREMENT, usuario TEXT, tipo TEXT, categoria TEXT, descripcion TEXT, monto REAL, fecha TEXT)')
    conn.commit()
    return conn

conn = conectar_db()
cursor = conn.cursor()

# --- SESIÓN ---
for k in ['autenticado', 'user', 'datos', 'carrito']:
    if k not in st.session_state: st.session_state[k] = False if k=='autenticado' else ('' if k=='user' else ({} if k=='datos' else []))

# --- LOGIN ---
if not st.session_state.autenticado:
    st.title("🚀 SaaS Taller - Acceso")
    t1, t2 = st.tabs(["Ingresar", "Registrar"])
    with t2:
        with st.form("r"):
            u, p = st.text_input("Email"), st.text_input("Pass", type="password")
            nom, dir_t, tel, cui = st.text_input("Taller"), st.text_input("Dir"), st.text_input("Tel"), st.text_input("CUIT")
            if st.form_submit_button("Crear"):
                try:
                    cursor.execute("INSERT INTO usuarios VALUES (?,?,?,?,?,?)", (u, hashlib.sha256(p.encode()).hexdigest(), nom, dir_t, tel, cui))
                    conn.commit(); st.success("¡OK!")
                except: st.error("Error")
    with t1:
        u_l, p_l = st.text_input("Email"), st.text_input("Pass", type="password", key="lp")
        if st.button("Entrar"):
            r = cursor.execute("SELECT password, taller, direccion, tel, cuit FROM usuarios WHERE user=?", (u_l,)).fetchone()
            if r and r[0] == hashlib.sha256(p_l.encode()).hexdigest():
                st.session_state.update({'autenticado':True, 'user':u_l, 'datos':{"taller":r[1],"dir":r[2],"tel":r[3],"cuit":r[4]}})
                st.rerun()
    st.stop()

user_act = st.session_state.user
info = st.session_state.datos

# --- SIDEBAR & LOGOUT ---
st.sidebar.title(f"🛠️ {info.get('taller')}")
if st.sidebar.button("Cerrar Sesión"):
    st.session_state.autenticado = False
    st.rerun()

st.markdown("<style>@media print { .no-print, button, .stSidebar, header, [data-testid='stHeader'], [data-testid='stExpander'], .stForm, .stTabs [data-baseweb='tab-list'] { display: none !important; } .print-header { text-align: center; border-bottom: 2px solid black; } }</style>", unsafe_allow_html=True)

tab_p, tab_i, tab_f = st.tabs(["📄 PRESUPUESTO", "📦 INVENTARIO", "📊 DASHBOARD"])

with tab_p:
    st.markdown(f"<div class='print-header'><h1>{info.get('taller','').upper()}</h1><p>{info.get('dir','')} | Tel: {info.get('tel','')} | {info.get('cuit','')}</p></div>", unsafe_allow_html=True)
    cliente_p = st.text_input("👤 Cliente / Vehículo", key="cp")
    
    with st.expander("➕ Cargar Ítem", expanded=True):
        items = cursor.execute("SELECT sku, repuesto, precio FROM inventario WHERE usuario=?", (user_act,)).fetchall()
        # Guardamos el precio como valor en el diccionario
        opc_dict = {f"{r[0]} | {r[1]}": (r[0], r[2]) for r in items}
        sel = st.selectbox("Stock", ["---"] + list(opc_dict.keys()))
        man = st.text_input("O Manual")
        c1, c2 = st.columns(2)
        can = c1.number_input("Cant.", min_value=1, value=1)
        
        # FIX: Extraemos solo el precio (índice 1 de la tupla guardada)
        val_sug = opc_dict.get(sel, (None, 0.0))[1]
        pre = c2.number_input("Precio $", value=float(val_sug))
        
        if st.button("Añadir"):
            n_i = sel if sel != "---" else man
            sku_i = opc_dict.get(sel, (None, 0.0))[0]
            st.session_state.carrito.append({"item": n_i, "sku": sku_i, "cant": can, "pre": pre, "sub": can*pre, "es_s": sel != "---"})
            st.rerun()

    if st.session_state.carrito:
        df_p = pd.DataFrame(st.session_state.carrito)
        st.table(df_p[["item", "cant", "pre", "sub"]])
        total_v = df_p['sub'].sum()
        st.header(f"TOTAL: ${total_v:,.2f}")
        if st.button("🖨️ IMPRIMIR"): components.html("<script>window.parent.print();</script>", height=0)
        if st.button("🚀 FINALIZAR VENTA", type="primary"):
            for r in st.session_state.carrito:
                if r["es_s"]: cursor.execute("UPDATE inventario SET stock = stock - ? WHERE sku = ? AND usuario = ?", (r["cant"], r["sku"], user_act))
            cursor.execute("INSERT INTO movimientos (usuario, tipo, categoria, descripcion, monto, fecha) VALUES (?,?,?,?,?,?)", (user_act, "INGRESO", "VENTA", f"Cliente: {cliente_p}", total_v, datetime.now().strftime('%Y-%m-%d')))
            conn.commit(); st.session_state.carrito = []; st.success("Venta guardada"); st.rerun()

with tab_i:
    st.header("📦 Mi Almacén")
    with st.form("inv"):
        c1, c2, c3, c4 = st.columns(4)
        f_s, f_n, f_c, f_p = c1.text_input("SKU"), c2.text_input("Nombre"), c3.number_input("Cant.", min_value=0), c4.number_input("Precio", min_value=0.0)
        if st.form_submit_button("Actualizar Stock"):
            if f_s:
                ex = cursor.execute("SELECT stock FROM inventario WHERE usuario=? AND sku=?", (user_act, f_s)).fetchone()
                if ex: cursor.execute("UPDATE inventario SET stock=stock+?, precio=? WHERE usuario=? AND sku=?", (f_c, f_p, user_act, f_s))
                else: cursor.execute("INSERT INTO inventario (usuario, sku, repuesto, stock, precio) VALUES (?,?,?,?,?)", (user_act, f_s, f_n, f_c, f_p))
                conn.commit(); st.rerun()
    st.dataframe(pd.read_sql_query("SELECT sku, repuesto, stock, precio FROM inventario WHERE usuario=?", conn, params=(user_act,)), use_container_width=True, hide_index=True)

with tab_f:
    st.header("📊 Dashboard Financiero")
    # Buscador por fecha
    f_inicio, f_fin = st.columns(2)
    d_ini = f_inicio.date_input("Desde", value=datetime.now())
    d_fin = f_fin.date_input("Hasta", value=datetime.now())

    with st.expander("💸 Registrar Gasto Manual"):
        g1, g2, g3 = st.columns(3)
        g_cat = g1.selectbox("Categoría", ["PROVEEDOR", "SUELDOS", "ALQUILER", "IMPUESTOS", "OTROS"])
        g_desc = g2.text_input("Descripción")
        g_monto = g3.number_input("Monto $", min_value=0.0)
        if st.button("Guardar Gasto"):
            cursor.execute("INSERT INTO movimientos (usuario, tipo, categoria, descripcion, monto, fecha) VALUES (?,?,?,?,?,?)", (user_act, "EGRESO", g_cat, g_desc, g_monto, datetime.now().strftime('%Y-%m-%d')))
            conn.commit(); st.rerun()

    df_m = pd.read_sql_query("SELECT * FROM movimientos WHERE usuario=? AND fecha BETWEEN ? AND ?", conn, params=(user_act, d_ini.strftime('%Y-%m-%d'), d_fin.strftime('%Y-%m-%d')))
    if not df_m.empty:
        c1, c2, c3 = st.columns(3)
        ing = df_m[df_m['tipo'] == 'INGRESO']['monto'].sum()
        egr = df_m[df_m['tipo'] == 'EGRESO']['monto'].sum()
        c1.metric("Ingresos", f"${ing:,.2f}")
        col2_label = "Egresos"
        c2.metric(col2_label, f"${egr:,.2f}", delta_color="inverse")
        c3.metric("Utilidad", f"${ing - egr:,.2f}")
        st.subheader("📈 Evolución")
        st.line_chart(df_m.groupby('fecha')['monto'].sum())
        st.dataframe(df_m.sort_values('fecha', ascending=False), use_container_width=True, hide_index=True)
