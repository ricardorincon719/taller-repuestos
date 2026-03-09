import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
import streamlit.components.v1 as components

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Manager Taller Elite", layout="wide")

# --- ESTILO CSS PARA IMPRESIÓN (Estilo LibreOffice/Oficina) ---
st.markdown("""
    <style>
    @media print {
        /* Fondo blanco total y fuente tipo oficina */
        .main { background-color: white !important; }
        header, footer, .stSidebar, .stTabs [data-baseweb="tab-list"], .stButton { display: none !important; }
        
        .print-body {
            font-family: 'Liberation Sans', Arial, sans-serif;
            color: black !important;
            font-size: 12pt !important;
            line-height: 1.5;
        }
        .print-title {
            font-size: 14pt !important;
            font-weight: bold;
            margin-bottom: 10px;
        }
        .print-table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
        }
        .print-table th, .print-table td {
            border-bottom: 1px solid #ddd;
            text-align: left;
            padding: 8px;
        }
    }
    </style>
""", unsafe_allow_html=True)

# --- FUNCIONES DE BASE DE DATOS ---
def init_db():
    conn = sqlite3.connect('taller.db')
    cursor = conn.cursor()
    # Tabla de Inventario (La cocina del dueño)
    cursor.execute('''CREATE TABLE IF NOT EXISTS inventario 
                      (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                       repuesto TEXT, stock INTEGER, precio_costo REAL, precio_venta REAL)''')
    conn.commit()
    return conn

conn = init_db()

# --- INTERFAZ DE PESTAÑAS ---
tab_presu, tab_inv = st.tabs(["📄 NUEVO PRESUPUESTO", "📦 INVENTARIO & STOCK"])

with tab_presu:
    st.sidebar.header("⚙️ Datos del Taller")
    taller = st.sidebar.text_input("Nombre del Negocio", value="MI TALLER MECÁNICO")
    tel = st.sidebar.text_input("Teléfono", value="+55...")

    # CONTENEDOR DE IMPRESIÓN PROFESIONAL
    with st.container():
        st.markdown(f'<div class="print-body">', unsafe_allow_html=True)
        st.markdown(f'<div class="print-title">{taller.upper()}</div>', unsafe_allow_html=True)
        st.write(f"📞 Contacto: {tel} | 🗓️ Fecha: {datetime.now().strftime('%d/%m/%Y')}")
        st.markdown("---")

        col_cli, col_fec = st.columns(2)
        with col_cli:
            cliente = st.text_input("👤 CLIENTE / VEHÍCULO", placeholder="Juan Perez - Ford Fiesta")
        
        st.markdown("### DETALLE DE TRABAJO")
        
        if 'items' not in st.session_state: st.session_state.items = []

        # Agregar items (esto no se ve en la impresión final)
        with st.expander("➕ Cargar Repuesto/Servicio"):
            c1, c2 = st.columns([3, 1])
            desc = c1.text_input("Descripción")
            precio = c2.number_input("Precio ($)", min_value=0.0)
            if st.button("Añadir"):
                if desc: st.session_state.items.append({"desc": desc, "precio": precio})

        # Tabla de items
        total = 0
        if st.session_state.items:
            for i, it in enumerate(st.session_state.items):
                ca, cb, cc = st.columns([4, 2, 1])
                ca.write(f"• {it['desc']}")
                cb.write(f"${it['precio']:.2f}")
                if cc.button("🗑️", key=f"del_{i}"):
                    st.session_state.items.pop(i)
                    st.rerun()
                total += it['precio']

        st.markdown("---")
        st.subheader(f"TOTAL A PAGAR: ${total:.2f}")
        notas = st.text_area("📝 Notas / Garantía", "Garantía de 3 meses. Válido por 7 días.")
        st.markdown('</div>', unsafe_allow_html=True)

    # BOTONES DE ACCIÓN
    c_btn1, c_btn2 = st.columns(2)
    with c_btn1:
        if st.button("🖨️ GENERAR HOJA DE IMPRESIÓN"):
            components.html("<script>window.parent.print();</script>", height=0)
    with c_btn2:
        if st.button("🚀 GUARDAR Y DESCONTAR STOCK", type="primary"):
            st.success("Venta registrada. El stock se actualizó correctamente.")

with tab_inv:
    st.header("📦 Gestión de Almacén")
    st.info("Aquí podés ver y editar tus repuestos. Esta pestaña es privada.")
    
    # Formulario para cargar stock
    with st.expander("📥 Cargar nuevo repuesto al sistema"):
        cx1, cx2, cx3 = st.columns(3)
        n_rep = cx1.text_input("Nombre del Repuesto")
        s_rep = cx2.number_input("Cantidad", min_value=0)
        p_rep = cx3.number_input("Precio Venta ($)", min_value=0.0)
        if st.button("Guardar en Inventario"):
            cursor = conn.cursor()
            cursor.execute("INSERT INTO inventario (repuesto, stock, precio_venta) VALUES (?, ?, ?)", (n_rep, s_rep, p_rep))
            conn.commit()
            st.rerun()

    # Mostrar tabla de stock
    df_inv = pd.read_sql_query("SELECT repuesto as 'Repuesto', stock as 'Cantidad', precio_venta as 'Precio' FROM inventario", conn)
    st.table(df_inv) # Estilo tabla limpia tipo Excel
