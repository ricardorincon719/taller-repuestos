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
nombre_taller = st.sidebar.text_input("Nombre del Taller", value="MI TALLER MECÁNICO")
contacto_taller = st.sidebar.text_input("Teléfono / WhatsApp", value="+54 9...")
direccion_taller = st.sidebar.text_input("Dirección / Ubicación", value="Calle Falsa 123")

# --- ENCABEZADO DEL PRESUPUESTO (Lo que ve el cliente) ---
st.title(f"🛠️ {nombre_taller}")
st.markdown(f"**📞 Contacto:** {contacto_taller} | **📍 Ubicación:** {direccion_taller}")
st.markdown(f"*Fecha: {datetime.now().strftime('%d/%m/%Y')}*")
st.markdown("---")

# --- DATOS DEL CLIENTE ---
cliente = st.text_input("👤 Nombre del Cliente", placeholder="Ej: Juan Pérez - Ford Fiesta")

if 'mis_repuestos' not in st.session_state:
    st.session_state.mis_repuestos = []

mano_obra = st.number_input("🔧 Mano de obra ($)", min_value=0.0, step=10.0)

with st.expander("➕ AGREGAR REPUESTOS / MATERIALES"):
    n_item = st.text_input("Descripción del repuesto")
    p_item = st.number_input("Precio unitario ($)", min_value=0.0)
    if st.button("Añadir a la lista"):
        if n_item and p_item > 0:
            st.session_state.mis_repuestos.append({"nombre": n_item, "precio": p_item})
            st.rerun()

# --- TABLA DE DETALLE ---
total_repuestos = sum(it['precio'] for it in st.session_state.mis_repuestos)
total_general = total_repuestos + mano_obra

if st.session_state.mis_repuestos:
    st.subheader("📋 Detalle de Reparación")
    for i, item in enumerate(st.session_state.mis_repuestos):
        c_a, c_b, c_c = st.columns([3, 1, 1])
        c_a.write(f"• {item['nombre']}")
        c_b.write(f"${item['precio']:.2f}")
        if c_c.button("❌", key=f"del_{i}"):
            st.session_state.mis_repuestos.pop(i)
            st.rerun()

st.markdown("---")
st.subheader(f"Suma Repuestos: ${total_repuestos:.2f}")
st.header(f"TOTAL A PAGAR: ${total_general:.2f}")

# --- BOTONES DE PODER ---
c1, c2, c3 = st.columns(3)
with c1:
    if st.button("🖨️ IMPRIMIR / PDF"):
        components.html("<script>window.parent.print();</script>", height=0)

with c2:
    if st.button("🚀 GUARDAR VENTA", type="primary"):
        if cliente:
            conn = conectar_db()
            cursor = conn.cursor()
            detalle_str = str(st.session_state.mis_repuestos)
            cursor.execute("INSERT INTO presupuestos (fecha, cliente, total, detalle) VALUES (?, ?, ?, ?)",
                           (datetime.now().strftime("%Y-%m-%d %H:%M"), cliente, total_general, detalle_str))
            conn.commit()
            conn.close()
            st.balloons()
            st.success(f"Presupuesto de {cliente} guardado.")
        else:
            st.warning("⚠️ Ingresá el nombre del cliente para guardar.")

with c3:
    if st.button("🗑️ NUEVO"):
        st.session_state.mis_repuestos = []
        st.rerun()

# --- EL ARCHIVO DE ÉXITO (HISTORIAL) ---
st.markdown("---")
with st.expander("📂 HISTORIAL DE TRABAJOS REALIZADOS"):
    conn = conectar_db()
    try:
        df_historial = pd.read_sql_query("SELECT fecha, cliente, total FROM presupuestos ORDER BY id DESC", conn)
        if not df_historial.empty:
            st.table(df_historial) # Usamos tabla fija para que se vea mejor al imprimir reportes
        else:
            st.info("No hay registros en la base de datos.")
    except:
        st.write("Esperando primer registro...")
    conn.close()
