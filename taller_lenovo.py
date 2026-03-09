import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
import streamlit.components.v1 as components

st.set_page_config(page_title="Taller Pro", layout="wide")

# --- CONEXIÓN Y BASE DE DATOS ---
def conectar_db():
    conn = sqlite3.connect('taller.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS inventario 
                      (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                       repuesto TEXT UNIQUE, stock INTEGER, precio_venta REAL)''')
    conn.commit()
    return conn

conn = conectar_db()
cursor = conn.cursor()

# --- CSS IMPRESIÓN MEJORADO ---
st.markdown("""
    <style>
    @media print {
        /* Oculta Sidebar, Botones, Cabeceras de Streamlit y el expansor de carga */
        .no-print, button, .stSidebar, header, [data-testid="stHeader"], .st-expanderHeader, .st-expanderContent, [data-testid="stExpander"] { 
            display: none !important; 
        }
        
        /* Asegura que el cuerpo de la impresión sea limpio */
        .print-header { 
            text-align: center; 
            margin-bottom: 20px; 
            border-bottom: 2px solid #000; 
            padding-bottom: 10px; 
        }
        .print-body { 
            font-family: Arial, sans-serif; 
            color: black; 
        }
        
        /* Ajusta las tablas para que ocupen todo el ancho en el papel */
        .stTable { 
            font-size: 11pt; 
            width: 100% !important; 
        }
    }
    </style>
""", unsafe_allow_html=True)

# --- SIDEBAR: DATOS DEL TALLER (EDITABLES) ---
st.sidebar.header("🏢 Datos de Mi Taller")
nombre_taller = st.sidebar.text_input("Nombre del Negocio", "MI TALLER MECÁNICO")
direccion_taller = st.sidebar.text_input("Dirección", "Calle Falsa 123")
telefono_taller = st.sidebar.text_input("Teléfono / WhatsApp", "+54 9...")
cuit_taller = st.sidebar.text_input("CUIT / Documento", "30-12345678-9")

if 'carrito' not in st.session_state:
    st.session_state.carrito = []

tab1, tab2 = st.tabs(["📄 PRESUPUESTO", "📦 INVENTARIO"])

with tab1:
    # --- ENCABEZADO DE IMPRESIÓN ---
    st.markdown(f"""
        <div class="print-header">
            <h1 style='margin:0;'>{nombre_taller.upper()}</h1>
            <p style='margin:0;'>{direccion_taller} | Tel: {telefono_taller}</p>
            <p style='margin:0;'>{cuit_taller}</p>
        </div>
    """, unsafe_allow_html=True)

    col_c, col_f = st.columns(2)
    cliente = col_c.text_input("👤 Cliente / Vehículo", placeholder="Ej: Juan Pérez - Toyota Hilux")
    col_f.write(f"📅 **Fecha:** {datetime.now().strftime('%d/%m/%Y')}")

    with st.expander("➕ Cargar Ítem al Listado", expanded=True):
        c1, c2, c3 = st.columns([3, 1, 1])
        
        items_db = cursor.execute("SELECT repuesto, precio_venta FROM inventario").fetchall()
        opciones = {r[0]: r[1] for r in items_db}
        
        seleccion = c1.selectbox("Elegir del Inventario", ["---"] + list(opciones.keys()))
        desc_manual = c1.text_input("O escribir Servicio/Mano de Obra")
        
        cant = c2.number_input("Cantidad", min_value=1, value=1)
        
        precio_sug = opciones[seleccion] if seleccion != "---" else 0.0
        precio_u = c3.number_input("Precio Unitario $", min_value=0.0, value=float(precio_sug))

        if st.button("Añadir"):
            nombre_final = seleccion if seleccion != "---" else desc_manual
            if nombre_final:
                st.session_state.carrito.append({
                    "item": nombre_final,
                    "cantidad": cant,
                    "precio_u": precio_u,
                    "subtotal": cant * precio_u,
                    "es_stock": seleccion != "---"
                })
                st.rerun()

    if st.session_state.carrito:
        st.markdown("### 🛠️ Detalle del Presupuesto")
        df_presu = pd.DataFrame(st.session_state.carrito)
        st.table(df_presu[["item", "cantidad", "precio_u", "subtotal"]])
        
        total = df_presu["subtotal"].sum()
        st.markdown(f"<h2 style='text-align: right;'>TOTAL: ${total:,.2f}</h2>", unsafe_allow_html=True)

        ba, bb, bc = st.columns(3)
        with ba:
            if st.button("🖨️ IMPRIMIR"):
                components.html("<script>window.parent.print();</script>", height=0)
        with bb:
            if st.button("🚀 FINALIZAR Y DESCONTAR", type="primary"):
                for row in st.session_state.carrito:
                    if row["es_stock"]:
                        cursor.execute("UPDATE inventario SET stock = stock - ? WHERE repuesto = ?", 
                                     (row["cantidad"], row["item"]))
                conn.commit()
                st.success("✅ Venta registrada y Stock actualizado.")
                st.session_state.carrito = []
                st.rerun()
        with bc:
            if st.button("🗑️ VACIAR"):
                st.session_state.carrito = []
                st.rerun()

with tab2:
    st.title("📦 Control de Almacén")
    with st.form("stock_form"):
        f1, f2, f3 = st.columns(3)
        n = f1.text_input("Nombre Repuesto")
        s = f2.number_input("Stock Inicial", min_value=0)
        p = f3.number_input("Precio Venta", min_value=0.0)
        if st.form_submit_button("Guardar"):
            cursor.execute("INSERT OR REPLACE INTO inventario (repuesto, stock, precio_venta) VALUES (?, ?, ?)", (n, s, p))
            conn.commit()
            st.rerun()
    st.markdown("---")
    inventario_df = pd.read_sql_query("SELECT repuesto as 'Repuesto', stock as 'Stock', precio_venta as 'Precio' FROM inventario", conn)
    st.dataframe(inventario_df, use_container_width=True, hide_index=True)

            st.rerun()

    df_stock = pd.read_sql_query("SELECT repuesto, stock, precio_venta FROM inventario", conn)
    st.dataframe(df_stock, use_container_width=True)
