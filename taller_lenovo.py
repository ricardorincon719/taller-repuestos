import streamlit as st
import pandas as pd
from datetime import datetime
import streamlit.components.v1 as components

st.set_page_config(page_title="Presupuestador Lenovo", page_icon="🛠️")
st.title("💰 Presupuestador de Taller")

if 'mis_repuestos' not in st.session_state:
    st.session_state.mis_repuestos = []

def cargar_ejemplo():
    st.session_state.mis_repuestos = [
        {"nombre": "Filtro de aceite", "precio": 25.0},
        {"nombre": "Líquido de frenos", "precio": 45.0},
        {"nombre": "Pastillas de freno", "precio": 120.0}
    ]

def limpiar_lista():
    st.session_state.mis_repuestos = []
    st.rerun()

mano_obra = st.number_input("Mano de obra ($)", min_value=0.0, step=10.0)

with st.expander("➕ AGREGAR REPUESTOS / ÍTEMS"):
    n_item = st.text_input("Nombre del repuesto/ítem", key="n_item")
    p_item = st.number_input("Precio ($)", min_value=0.0, key="p_item")
    if st.button("Añadir a la lista"):
        if n_item and p_item > 0:
            st.session_state.mis_repuestos.append({"nombre": n_item, "precio": p_item})
            st.rerun()

total_repuestos = 0
# Contenedor para la impresión
with st.container():
    st.markdown('<div id="seccion-imprimir">', unsafe_allow_html=True)
    if st.session_state.mis_repuestos:
        st.subheader("📋 Detalle de Repuestos")
        for i, item in enumerate(st.session_state.mis_repuestos):
            c_a, c_b, c_c = st.columns([3, 2, 1])
            c_a.write(f"• {item['nombre']}")
            c_b.write(f"${item['precio']:.2f}")
            if c_c.button("❌", key=f"del_{i}"):
                st.session_state.mis_repuestos.pop(i)
                st.rerun()
        
        total_repuestos = sum(it['precio'] for it in st.session_state.mis_repuestos)

    total_general = total_repuestos + mano_obra

    st.markdown("---")
    st.subheader(f"Suma de Repuestos: ${total_repuestos:.2f}")
    st.header(f"TOTAL GENERAL: ${total_general:.2f}")
    st.markdown('</div>', unsafe_allow_html=True)

st.markdown("---")
c1, c2, c3 = st.columns(3)

with c1:
    if st.button("📝 Ejemplo"):
        cargar_ejemplo()
        st.rerun()

with c2:
    if st.button("🗑️ Limpiar"):
        limpiar_lista()

with c3:
    # Botón mágico de impresión
    if st.button("🖨️ IMPRIMIR / PDF"):
        components.html(
            """
            <script>
                window.parent.print();
            </script>
            """,
            height=0,
        )

# Sección de Exportación a CSV oculta del PDF
with st.expander("💾 Opciones de Guardado"):
    datos_exportar = st.session_state.mis_repuestos + [{"nombre": "Mano de Obra", "precio": mano_obra}]
    datos_exportar.append({"nombre": "TOTAL FINAL", "precio": total_general})
    df = pd.DataFrame(datos_exportar)
    csv = df.to_csv(index=False).encode('utf-8')
    st.download_button("Descargar Archivo CSV", data=csv, file_name="presupuesto.csv")
