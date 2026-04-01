import streamlit as st
from datetime import datetime
import json

st.set_page_config(page_title="Taller Presupuestos", page_icon="🔧", layout="wide")

st.title("🔧 Taller Presupuestos")

# Inicializar datos en session_state
if 'presupuestos' not in st.session_state:
    st.session_state.presupuestos = []
if 'items_actuales' not in st.session_state:
    st.session_state.items_actuales = []

# Sidebar con resumen
with st.sidebar:
    st.header("📊 Resumen")
    total_presupuestos = len(st.session_state.presupuestos)
    total_facturado = sum(p.get('total', 0) for p in st.session_state.presupuestos)
    st.metric("Presupuestos", total_presupuestos)
    st.metric("Total Facturado", f"${total_facturado:,.2f}")
    
    st.markdown("---")
    if st.button("📤 Exportar datos (JSON)"):
        json_str = json.dumps(st.session_state.presupuestos, indent=2)
        st.download_button("Descargar JSON", json_str, "presupuestos.json", "application/json")

# Pestañas principales
tab1, tab2, tab3 = st.tabs(["💰 Nuevo Presupuesto", "📋 Historial", "📊 Estadísticas"])

# ==================== TAB 1: NUEVO PRESUPUESTO ====================
with tab1:
    st.subheader("📝 Datos del cliente")
    col1, col2 = st.columns(2)
    with col1:
        cliente_nombre = st.text_input("Nombre del cliente *", placeholder="Ej: Juan Pérez")
        telefono = st.text_input("Teléfono", placeholder="Ej: 123456789")
    with col2:
        email = st.text_input("Email", placeholder="cliente@email.com")
        notas = st.text_area("Notas adicionales", placeholder="Observaciones...")
    
    st.markdown("---")
    
    col1, col2 = st.columns(2)
    with col1:
        repuestos = st.number_input("🔧 Repuestos ($)", min_value=0.0, step=10.0, value=0.0)
    with col2:
        mano_obra = st.number_input("👨‍🔧 Mano de obra ($)", min_value=0.0, step=10.0, value=0.0)
    
    st.markdown("---")
    
    # Items adicionales
    st.subheader("➕ Items adicionales")
    col_a, col_b, col_c = st.columns([3, 2, 1])
    with col_a:
        item_nombre = st.text_input("Nombre del ítem", key="nuevo_item_nombre")
    with col_b:
        item_precio = st.number_input("Precio", min_value=0.0, key="nuevo_item_precio")
    with col_c:
        if st.button("➕ Agregar", key="btn_agregar_item"):
            if item_nombre and item_precio > 0:
                st.session_state.items_actuales.append({
                    "nombre": item_nombre,
                    "precio": item_precio
                })
                st.success(f"✅ '{item_nombre}' agregado")
                st.rerun()
    
    # Mostrar items agregados
    if st.session_state.items_actuales:
        st.write("**Items agregados:**")
        for i, item in enumerate(st.session_state.items_actuales):
            col_a, col_b, col_c = st.columns([3, 2, 1])
            col_a.write(f"• {item['nombre']}")
            col_b.write(f"${item['precio']:.2f}")
            if col_c.button("❌", key=f"del_item_{i}"):
                st.session_state.items_actuales.pop(i)
                st.rerun()
    
    # Calcular total
    total_items = sum(i['precio'] for i in st.session_state.items_actuales)
    total_general = repuestos + mano_obra + total_items
    
    st.markdown("---")
    st.markdown(f"### 💰 TOTAL DEL PRESUPUESTO: **${total_general:,.2f}**")
    
    # Botón guardar
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("💾 GUARDAR PRESUPUESTO", type="primary", use_container_width=True):
            if not cliente_nombre:
                st.error("❌ Por favor ingrese el nombre del cliente")
            else:
                nuevo_id = len(st.session_state.presupuestos) + 1
                nuevo_presupuesto = {
                    "id": nuevo_id,
                    "fecha": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "cliente": cliente_nombre,
                    "telefono": telefono,
                    "email": email,
                    "repuestos": repuestos,
                    "mano_obra": mano_obra,
                    "items": st.session_state.items_actuales.copy(),
                    "total": total_general,
                    "notas": notas,
                    "estado": "PENDIENTE"
                }
                st.session_state.presupuestos.append(nuevo_presupuesto)
                st.session_state.items_actuales = []
                st.balloons()
                st.success(f"✅ Presupuesto #{nuevo_id} guardado correctamente!")
                st.rerun()

# ==================== TAB 2: HISTORIAL ====================
with tab2:
    if not st.session_state.presupuestos:
        st.info("📭 No hay presupuestos guardados aún. Crea uno en la pestaña 'Nuevo Presupuesto'.")
    else:
        # Filtro de búsqueda
        busqueda = st.text_input("🔍 Buscar por cliente", placeholder="Nombre...")
        
        presupuestos_filtrados = st.session_state.presupuestos
        if busqueda:
            presupuestos_filtrados = [p for p in presupuestos_filtrados if busqueda.lower() in p['cliente'].lower()]
        
        st.write(f"**Mostrando {len(presupuestos_filtrados)} de {len(st.session_state.presupuestos)} presupuestos**")
        
        for p in reversed(presupuestos_filtrados):
            with st.expander(f"📄 #{p['id']} - {p['cliente']} - ${p['total']:,.2f} - {p['estado']}"):
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"**Fecha:** {p['fecha']}")
                    st.write(f"**Teléfono:** {p['telefono'] or '—'}")
                    st.write(f"**Email:** {p['email'] or '—'}")
                with col2:
                    st.write(f"**Repuestos:** ${p['repuestos']:.2f}")
                    st.write(f"**Mano de obra:** ${p['mano_obra']:.2f}")
                    if p['items']:
                        st.write("**Items adicionales:**")
                        for item in p['items']:
                            st.write(f"  • {item['nombre']}: ${item['precio']:.2f}")
                
                if p['notas']:
                    st.write(f"**Notas:** {p['notas']}")
                
                # Cambiar estado
                estados = ["PENDIENTE", "APROBADO", "RECHAZADO", "FACTURADO"]
                estado_actual_idx = estados.index(p['estado'])
                nuevo_estado = st.selectbox(
                    "Cambiar estado",
                    estados,
                    index=estado_actual_idx,
                    key=f"estado_{p['id']}"
                )
                if nuevo_estado != p['estado']:
                    p['estado'] = nuevo_estado
                    st.success(f"✅ Estado actualizado a {nuevo_estado}")
                    st.rerun()

# ==================== TAB 3: ESTADÍSTICAS ====================
with tab3:
    if not st.session_state.presupuestos:
        st.info("📊 No hay datos suficientes para mostrar estadísticas.")
    else:
        st.subheader("📈 Resumen general")
        
        # Métricas
        col1, col2, col3 = st.columns(3)
        total = sum(p['total'] for p in st.session_state.presupuestos)
        promedio = total / len(st.session_state.presupuestos)
        
        with col1:
            st.metric("Total presupuestos", len(st.session_state.presupuestos))
        with col2:
            st.metric("Total facturado", f"${total:,.2f}")
        with col3:
            st.metric("Promedio por presupuesto", f"${promedio:,.2f}")
        
        st.markdown("---")
        
        # Distribución por estado (sin plotly, usando st.progress)
        st.subheader("📊 Distribución por estado")
        estados_count = {}
        for p in st.session_state.presupuestos:
            estado = p['estado']
            estados_count[estado] = estados_count.get(estado, 0) + 1
        
        for estado, count in estados_count.items():
            porcentaje = (count / len(st.session_state.presupuestos)) * 100
            st.write(f"**{estado}:** {count} presupuestos ({porcentaje:.1f}%)")
            st.progress(porcentaje / 100)
        
        st.markdown("---")
        
        # Top clientes
        st.subheader("🏆 Top 5 clientes por facturación")
        clientes_total = {}
        for p in st.session_state.presupuestos:
            cliente = p['cliente']
            clientes_total[cliente] = clientes_total.get(cliente, 0) + p['total']
        
        top_clientes = sorted(clientes_total.items(), key=lambda x: x[1], reverse=True)[:5]
        for cliente, total_cliente in top_clientes:
            st.write(f"**{cliente}:** ${total_cliente:,.2f}")
