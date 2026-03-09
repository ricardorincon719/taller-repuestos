import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
import streamlit.components.v1 as components

# --- CONFIGURACIÓN DE BASE DE DATOS ---
def conectar_db():
    conn = sqlite3.connect('taller.db')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS presupuestos 
                      (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                       fecha TEXT, cliente TEXT, total REAL, detalle TEXT)''')
    conn.commit()
    return conn

# --- CONFIGURACIÓN DEL TALLER (SIDEBAR) ---
st.sidebar.header("⚙️ Configuración del Taller")
nombre_taller = st.sidebar.text_input("Nombre del Taller", value="MI TALLER")
contacto_taller = st.sidebar.text_input("Contacto", value="+54 9...")

# --- INTERFAZ PRINCIPAL ---
st.title(f"💰 {nombre_taller}")
cliente = st.text_input("👤 Nombre del Cliente", placeholder="Ej: Juan Pérez")

if 'mis_repuestos' not in st.session_state:
    st.session_state.mis_repuestos = []

mano_obra = st.number_input("🛠️ Mano de obra ($)", min_value=0.0, step=10.0)

with st.expander("➕ AGREGAR REPUESTOS"):
    n_item = st.text_input("Nombre del repuesto")
    p_item = st.number_input("Precio ($)", min_value=0.0)
    if st.button("Añadir"):
        if n_item and p_item > 0:
            st.session_state.mis_repuestos.append({"nombre": n_item, "precio": p_item})
            st.rerun()

# --- CÁLCULOS Y VISTA ---
total_repuestos = sum(it['precio'] for it in st.session_state.mis_repuestos)
total_general = total_repuestos + mano_obra

if st.session_state.mis_repuestos:
    st.subheader("📋 Detalle")
    for i, item in enumerate(st.session_state.mis_repuestos):
        c_a, c_b, c_c = st.columns([3,2,1])
        c_a.write(f"• {item['nombre']}")
        c_b.write(f"${item['precio']:.2f}")
        if c_c.button("❌", key=f"del_{i}"):
            st.session_state.mis_repuestos.pop(i)
            st.rerun()

st.markdown("---")
st.header(f"TOTAL: ${total_general:.2f}")

# --- BOTONES DE ACCIÓN ---
c1, c2, c3 = st.columns(3)
with c1:
    if st.button("🖨️ IMPRIMIR / PDF"):
        components.html("<script>window.parent.print();</script>", height=0)

with c2:
    if st.button("🚀 FINALIZAR Y GUARDAR", type="primary"):
        if cliente:
            conn = conectar_db()
            cursor = conn.cursor()
            detalle_str = str(st.session_state.mis_repuestos)
            cursor.execute("INSERT INTO presupuestos (fecha, cliente, total, detalle) VALUES (?, ?, ?, ?)",
                           (datetime.now().strftime("%Y-%m-%d %H:%M"), cliente, total_general, detalle_str))
            conn.commit()
            conn.close()
            st.balloons()
            st.success("¡Guardado en el historial!")
        else:
            st.error("Por favor, poné el nombre del cliente.")

with c3:
    if st.button("🗑️ NUEVO"):
        st.session_state.mis_repuestos = []
        st.rerun()

# --- MÓDULO DE HISTORIAL (EL VALOR AGREGADO) ---
st.markdown("---")
with st.expander("📂 VER HISTORIAL DE VENTAS"):
    conn = conectar_db()
    df_historial = pd.read_sql_query("SELECT fecha, cliente, total FROM presupuestos ORDER BY id DESC", conn)
    conn.close()
    if not df_historial.empty:
        st.dataframe(df_historial, use_container_width=True)
        st.download_button("Descargar Reporte Excel (CSV)", 
                           df_historial.to_csv(index=False), 
                           "reporte_ventas.csv")
    else:
        st.write("No hay ventas registradas aún.")
