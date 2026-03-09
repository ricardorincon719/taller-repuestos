import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
import streamlit.components.v1 as components

st.set_page_config(page_title="Manager Taller Elite", layout="wide")

# --- BASE DE DATOS ---
def conectar_db():
    return sqlite3.connect('taller.db', check_same_thread=False)

conn = conectar_db()
cursor = conn.cursor()
cursor.execute('''CREATE TABLE IF NOT EXISTS inventario 
                  (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                   repuesto TEXT UNIQUE, stock INTEGER, precio_venta REAL)''')
conn.commit()

# --- CSS PARA IMPRESIÓN ---
st.markdown("""
    <style>
    @media print {
        header, .stSidebar, .stTabs [data-baseweb="tab-list"], .no-print, button { display: none !important; }
        .print-body { font-family: Arial; color: black; }
        .stTable { font-size: 10pt; }
    }
    </style>
""", unsafe_allow_html=True)

tab_presu, tab_inv = st.tabs(["📄 PRESUPUESTO", "📦 INVENTARIO"])

if 'carrito' not in st.session_state:
    st.session_state.carrito = []

with tab_presu:
    st.sidebar.header("Configuración")
    taller = st.sidebar.text_input("Taller", "MI TALLER MECÁNICO")
    
    st.markdown(f"### {taller}")
    st.write(f"Fecha: {datetime.now().strftime('%d/%m/%Y')}")
    cliente = st.text_input("Cliente / Vehículo")

    # AGREGAR ÍTEMS CON CANTIDAD
    with st.expander("➕ Agregar Ítem al Presupuesto", expanded=True):
        # Traemos productos del inventario para el buscador
        res = cursor.execute("SELECT repuesto, precio_venta FROM inventario").fetchall()
        opciones = {r[0]: r[1] for r in res}
        
        col1, col2, col3 = st.columns([3, 1, 1])
        item_nom = col1.selectbox("Seleccionar Repuesto", options=["---"] + list(opciones.keys()))
        cant = col2.number_input("Cantidad", min_value=1, value=1)
        
        # Si es un servicio manual (que no está en stock)
        item_manual = col1.text_input("O escribir ítem/servicio manualmente")
        precio_manual = col3.number_input("Precio unitario $", min_value=0.0)

        if st.button("Añadir"):
            nombre_final = item_nom if item_nom != "---" else item_manual
            precio_final = opciones[item_nom] if item_nom != "---" else precio_manual
            if nombre_final:
                st.session_state.carrito.append({
                    "desc": nombre_final, 
                    "cant": cant, 
                    "precio": precio_final,
                    "es_repuesto": item_nom != "---"
                })
                st.rerun()

    # MOSTRAR TABLA DE DETALLE
    if st.session_state.carrito:
        df_presu = pd.DataFrame(st.session_state.carrito)
        df_presu['Subtotal'] = df_presu['cant'] * df_presu['precio']
        st.table(df_presu[['desc', 'cant', 'precio', 'Subtotal']])
        
        total_final = df_presu['Subtotal'].sum()
        st.subheader(f"TOTAL: ${total_final:,.2f}")

    # BOTONES DE ACCIÓN
    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("🖨️ IMPRIMIR"):
            components.html("<script>window.parent.print();</script>", height=0)
    with c2:
        if st.button("🚀 GUARDAR Y DESCONTAR STOCK", type="primary"):
            for it in st.session_state.carrito:
                if it['es_repuesto']:
                    cursor.execute("UPDATE inventario SET stock = stock - ? WHERE repuesto = ?", (it['cant'], it['desc']))
            conn.commit()
            st.success("Stock actualizado correctamente.")
            st.session_state.carrito = [] # Limpiar después de vender
    with c3:
        if st.button("🧹 VACIAR"):
            st.session_state.carrito = []
            st.rerun()

with tab_inv:
    st.header("Gestión de Stock")
    with st.form("nuevo_item"):
        n, s, p = st.columns(3)
        nom = n.text_input("Repuesto")
        sto = s.number_input("Stock", min_value=0)
        pre = p.number_input("Precio Venta", min_value=0.0)
        if st.form_submit_button("Guardar en Inventario"):
            cursor.execute("INSERT OR REPLACE INTO inventario (repuesto, stock, precio_venta) VALUES (?, ?, ?)", (nom, sto, pre))
            conn.commit()
            st.rerun()

    df_stock = pd.read_sql_query("SELECT repuesto, stock, precio_venta FROM inventario", conn)
    st.dataframe(df_stock, use_container_width=True)
