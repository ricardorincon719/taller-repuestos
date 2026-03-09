import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
import streamlit.components.v1 as components

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Manager Taller Elite", layout="wide")

# --- ESTILO CSS PARA IMPRESIÓN ---
st.markdown("""
    <style>
    @media print {
        .main { background-color: white !important; }
        header, footer, .stSidebar, .stTabs [data-baseweb="tab-list"], .stButton, .no-print { display: none !important; }
        .print-body { font-family: 'Arial', sans-serif; color: black !important; font-size: 12pt !important; }
        .print-title { font-size: 14pt !important; font-weight: bold; text-transform: uppercase; }
    }
    </style>
""", unsafe_allow_html=True)

# --- FUNCIONES DE BASE DE DATOS ---
def conectar_db():
    conn = sqlite3.connect('taller.db', check_same_thread=False)
    return conn

conn = conectar_db()
cursor = conn.cursor()
cursor.execute('''CREATE TABLE IF NOT EXISTS inventario 
                  (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                   repuesto TEXT, stock INTEGER, precio_venta REAL)''')
conn.commit()

# --- INTERFAZ ---
tab_presu, tab_inv = st.tabs(["📄 NUEVO PRESUPUESTO", "📦 INVENTARIO & STOCK"])

if 'lista_trabajo' not in st.session_state:
    st.session_state.lista_trabajo = []

with tab_presu:
    st.sidebar.header("⚙️ Configuración")
    taller = st.sidebar.text_input("Nombre del Negocio", value="MI TALLER MECÁNICO")
    tel = st.sidebar.text_input("Teléfono", value="+54...")

    st.markdown('<div class="print-body">', unsafe_allow_html=True)
    st.markdown(f'<div class="print-title">{taller}</div>', unsafe_allow_html=True)
    st.write(f"📞 {tel} | 🗓️ {datetime.now().strftime('%d/%m/%Y')}")
    st.markdown("---")

    cliente = st.text_input("👤 CLIENTE / VEHÍCULO", placeholder="Ej: Juan Pérez - Ford Fiesta")
    
    st.markdown("### DETALLE DE TRABAJO")
    
    # Agregar items (no se ve al imprimir)
    with st.expander("➕ Cargar Repuesto o Servicio", expanded=True):
        c1, c2 = st.columns([3, 1])
        desc = c1.text_input("Descripción del ítem")
        precio = c2.number_input("Precio ($)", min_value=0.0, step=100.0)
        if st.button("Añadir a la lista"):
            if desc:
                st.session_state.lista_trabajo.append({"desc": desc, "precio": precio})
                st.rerun()

    # Tabla de items cargados
    total = 0
    for i, it in enumerate(st.session_state.lista_trabajo):
        ca, cb, cc = st.columns([6, 2, 1])
        ca.write(f"• {it['desc']}")
        cb.write(f"${it['precio']:.2f}")
        if cc.button("🗑️", key=f"del_{i}"):
            st.session_state.lista_trabajo.pop(i)
            st.rerun()
        total += it['precio']

    st.markdown("---")
    st.subheader(f"TOTAL: ${total:.2f}")
    notas = st.text_area("📝 Notas / Garantía", "Garantía de 3 meses. Válido por 7 días.")
    st.markdown('</div>', unsafe_allow_html=True)

    # ACCIONES
    col_b1, col_b2, col_b3 = st.columns([1,1,1])
    with col_b1:
        if st.button("🖨️ IMPRIMIR"):
            components.html("<script>window.parent.print();</script>", height=0)
    with col_b2:
        if st.button("🚀 GUARDAR Y DESCONTAR", type="primary"):
            # Lógica para descontar stock
            for it in st.session_state.lista_trabajo:
                cursor.execute("UPDATE inventario SET stock = stock - 1 WHERE repuesto = ?", (it['desc'],))
                
            conn.commit()
            st.success("¡Venta registrada y stock actualizado!")
    with col_b3:
        if st.button("🧹 LIMPIAR TODO"):
            st.session_state.lista_trabajo = []
            st.rerun()

with tab_inv:
    st.header("📦 Gestión de Almacén")
    
    with st.expander("📥 Cargar nuevo repuesto"):
        cx1, cx2, cx3 = st.columns(3)
        n_rep = cx1.text_input("Nombre")
        s_rep = cx2.number_input("Stock Inicial", min_value=0)
        p_rep = cx3.number_input("Precio Venta", min_value=0.0)
        if st.button("Registrar Repuesto"):
            cursor.execute("INSERT INTO inventario (repuesto, stock, precio_venta) VALUES (?, ?, ?)", (n_rep, s_rep, p_rep))
            conn.commit()
            st.rerun()

    st.markdown("### Stock Actual")
    df_inv = pd.read_sql_query("SELECT id, repuesto as 'Repuesto', stock as 'Cantidad', precio_venta as 'Precio' FROM inventario", conn)
    st.dataframe(df_inv, use_container_width=True, hide_index=True)
    
    if st.button("Actualizar Tabla"):
        st.rerun()

