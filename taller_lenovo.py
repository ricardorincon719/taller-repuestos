import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
import streamlit.components.v1 as components

st.set_page_config(page_title="Taller Pro", layout="wide")

def conectar_db():
    conn = sqlite3.connect('taller.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('CREATE TABLE IF NOT EXISTS inventario (id INTEGER PRIMARY KEY AUTOINCREMENT, repuesto TEXT UNIQUE, stock INTEGER, precio_venta REAL)')
    conn.commit()
    return conn

conn = conectar_db()
cursor = conn.cursor()

st.markdown("<style>@media print { .no-print, button, .stSidebar, header, [data-testid='stHeader'], .st-expanderHeader, .st-expanderContent, [data-testid='stExpander'] { display: none !important; } .print-header { text-align: center; margin-bottom: 20px; border-bottom: 2px solid #000; } }</style>", unsafe_allow_html=True)

st.sidebar.header("🏢 Datos del Taller")
nombre_t = st.sidebar.text_input("Nombre", "MI TALLER MECÁNICO")
dir_t = st.sidebar.text_input("Dirección", "Calle 123")
tel_t = st.sidebar.text_input("Teléfono", "+54...")

if 'carrito' not in st.session_state:
    st.session_state.carrito = []

t1, t2 = st.tabs(["📄 PRESUPUESTO", "📦 INVENTARIO"])

with t1:
    st.markdown(f"<div class='print-header'><h1>{nombre_t.upper()}</h1><p>{dir_t} | Tel: {tel_t}</p></div>", unsafe_allow_html=True)
    c_nom = st.text_input("👤 Cliente / Vehículo")
    st.write(f"📅 Fecha: {datetime.now().strftime('%d/%m/%Y')}")

    with st.expander("➕ Agregar Ítem", expanded=True):
        col1, col2, col3 = st.columns(3)
        db_res = cursor.execute("SELECT repuesto, precio_venta FROM inventario").fetchall()
        opc = {r[0]: r[1] for r in db_res}
        sel = col1.selectbox("Stock", ["---"] + list(opc.keys()))
        man = col1.text_input("O Servicio Manual")
        can = col2.number_input("Cant.", min_value=1, value=1)
        pre_s = opc[sel] if sel != "---" else 0.0
        pre_u = col3.number_input("Precio $", min_value=0.0, value=float(pre_s))
        if st.button("Añadir"):
            n_final = sel if sel != "---" else man
            if n_final:
                st.session_state.carrito.append({"item": n_final, "cant": can, "pre": pre_u, "sub": can * pre_u, "es_s": sel != "---"})
                st.rerun()

    if st.session_state.carrito:
        df_p = pd.DataFrame(st.session_state.carrito)
        st.table(df_p[["item", "cant", "pre", "sub"]])
        st.header(f"TOTAL: ${df_p['sub'].sum():,.2f}")
        b1, b2, b3 = st.columns(3)
        if b1.button("🖨️ IMPRIMIR"):
            components.html("<script>window.parent.print();</script>", height=0)
        if b2.button("🚀 FINALIZAR", type="primary"):
            for r in st.session_state.carrito:
                if r["es_s"]:
                    cursor.execute("UPDATE inventario SET stock = stock - ? WHERE repuesto = ?", (r["cant"], r["item"]))
            conn.commit()
            st.session_state.carrito = []
            st.success("Venta guardada")
            st.rerun()
        if b3.button("🗑️ VACIAR"):
            st.session_state.carrito = []
            st.rerun()

with t2:
    st.header("📦 Inventario")
    with st.form("f_inv"):
        i1, i2, i3 = st.columns(3)
        n_i = i1.text_input("Repuesto")
        s_i = i2.number_input("Stock", min_value=0)
        p_i = i3.number_input("Precio", min_value=0.0)
        if st.form_submit_button("Guardar"):
            cursor.execute("INSERT OR REPLACE INTO inventario (repuesto, stock, precio_venta) VALUES (?, ?, ?)", (n_i, s_i, p_i))
            conn.commit()
            st.rerun()
    df_i = pd.read_sql_query("SELECT repuesto, stock, precio_venta FROM inventario", conn)
    st.dataframe(df_i, use_container_width=True, hide_index=True)
