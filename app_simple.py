import streamlit as st
import pandas as pd
from datetime import datetime
import plotly.express as px
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
import io
import base64

st.set_page_config(page_title="Taller Presupuestos", page_icon="🔧", layout="wide")

st.title("🔧 Taller Presupuestos - Sistema Rápido")

# Inicializar session state
if 'presupuestos' not in st.session_state:
    st.session_state.presupuestos = []
if 'items_actuales' not in st.session_state:
    st.session_state.items_actuales = []

# Sidebar
with st.sidebar:
    st.header("📊 Resumen")
    if st.session_state.presupuestos:
        total_facturado = sum(p['total'] for p in st.session_state.presupuestos)
        st.metric("Presupuestos", len(st.session_state.presupuestos))
        st.metric("Total Facturado", f"${total_facturado:,.2f}")

# Pestañas
tab1, tab2, tab3 = st.tabs(["💰 Nuevo Presupuesto", "📋 Historial", "📊 Estadísticas"])

with tab1:
    st.subheader("Datos del cliente")
    col1, col2 = st.columns(2)
    with col1:
        cliente = st.text_input("Nombre del cliente *")
        telefono = st.text_input("Teléfono")
    with col2:
        email = st.text_input("Email")
        notas = st.text_area("Notas")
    
    st.markdown("---")
    col1, col2 = st.columns(2)
    with col1:
        repuestos = st.number_input("Repuestos ($)", min_value=0.0, step=10.0)
    with col2:
        mano_obra = st.number_input("Mano de obra ($)", min_value=0.0, step=10.0)
    
    st.markdown("---")
    st.subheader("Items adicionales")
    col_a, col_b, col_c = st.columns([3, 2, 1])
    with col_a:
        item_nombre = st.text_input("Nombre", key="item_nombre")
    with col_b:
        item_precio = st.number_input("Precio", min_value=0.0, key="item_precio")
    with col_c:
        if st.button("➕ Agregar"):
            if item_nombre and item_precio > 0:
                st.session_state.items_actuales.append({"nombre": item_nombre, "precio": item_precio})
                st.rerun()
    
    if st.session_state.items_actuales:
        for i, item in enumerate(st.session_state.items_actuales):
            col_a, col_b, col_c = st.columns([3, 2, 1])
            col_a.write(item['nombre'])
            col_b.write(f"${item['precio']:.2f}")
            if col_c.button("❌", key=f"del_{i}"):
                st.session_state.items_actuales.pop(i)
                st.rerun()
    
    total_items = sum(i['precio'] for i in st.session_state.items_actuales)
    total_general = repuestos + mano_obra + total_items
    
    st.markdown("---")
    col1, col2, col3 = st.columns(3)
    with col2:
        st.markdown(f"### TOTAL: ${total_general:,.2f}")
    
    col1, col2, col3 = st.columns(3)
    with col2:
        if st.button("💾 Guardar Presupuesto", type="primary"):
            if cliente:
                nuevo = {
                    "id": len(st.session_state.presupuestos) + 1,
                    "fecha": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "cliente": cliente,
                    "telefono": telefono,
                    "email": email,
                    "repuestos": repuestos,
                    "mano_obra": mano_obra,
                    "items": st.session_state.items_actuales.copy(),
                    "total": total_general,
                    "notas": notas,
                    "estado": "PENDIENTE"
                }
                st.session_state.presupuestos.append(nuevo)
                st.session_state.items_actuales = []
                st.success(f"✅ Presupuesto #{nuevo['id']} guardado!")
                st.rerun()
            else:
                st.error("Ingrese el nombre del cliente")

with tab2:
    if st.session_state.presupuestos:
        for p in reversed(st.session_state.presupuestos):
            with st.expander(f"#{p['id']} - {p['cliente']} - ${p['total']:,.2f} - {p['estado']}"):
                col1, col2 = st.columns(2)
                col1.write(f"**Fecha:** {p['fecha']}")
                col1.write(f"**Teléfono:** {p['telefono']}")
                col2.write(f"**Email:** {p['email']}")
                st.write("**Detalles:**")
                st.write(f"- Repuestos: ${p['repuestos']:.2f}")
                st.write(f"- Mano de obra: ${p['mano_obra']:.2f}")
                for item in p['items']:
                    st.write(f"- {item['nombre']}: ${item['precio']:.2f}")
                
                nuevo_estado = st.selectbox("Estado", ["PENDIENTE", "APROBADO", "RECHAZADO", "FACTURADO"], 
                                            index=["PENDIENTE", "APROBADO", "RECHAZADO", "FACTURADO"].index(p['estado']),
                                            key=f"estado_{p['id']}")
                if nuevo_estado != p['estado']:
                    p['estado'] = nuevo_estado
                    st.rerun()
    else:
        st.info("No hay presupuestos guardados")

with tab3:
    if st.session_state.presupuestos:
        df = pd.DataFrame(st.session_state.presupuestos)
        fig1 = px.pie(df, names='estado', title='Distribución por estado')
        st.plotly_chart(fig1, use_container_width=True)
        
        fig2 = px.bar(df, x='cliente', y='total', title='Presupuestos por cliente')
        st.plotly_chart(fig2, use_container_width=True)
        
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Descargar CSV", csv, "presupuestos.csv", "text/csv")
    else:
        st.info("No hay datos para mostrar")
