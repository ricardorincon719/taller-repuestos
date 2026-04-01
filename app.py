"""
Sistema de Presupuestos para Taller Mecánico
Autor: Ricardo Rincon
Versión: 2.0 - Profesional
"""

import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
import os
import json
from fpdf import FPDF
import plotly.express as px
import io
import base64

# Configuración de página
st.set_page_config(
    page_title="Taller Presupuestos",
    page_icon="🔧",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS personalizado
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(90deg, #1e3c72 0%, #2a5298 100%);
        padding: 1rem;
        border-radius: 10px;
        color: white;
        text-align: center;
        margin-bottom: 2rem;
    }
    .presupuesto-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 10px;
        border-left: 5px solid #2a5298;
        margin: 1rem 0;
    }
    .total-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1.5rem;
        border-radius: 10px;
        color: white;
        text-align: center;
    }
</style>
""", unsafe_allow_html=True)

# ==================== CONFIGURACIÓN DE BASE DE DATOS ====================

def init_database():
    """Inicializar la base de datos SQLite"""
    conn = sqlite3.connect('taller_presupuestos.db')
    c = conn.cursor()
    
    # Tabla de presupuestos
    c.execute('''CREATE TABLE IF NOT EXISTS presupuestos
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  fecha TEXT,
                  cliente_nombre TEXT,
                  cliente_telefono TEXT,
                  cliente_email TEXT,
                  repuestos REAL,
                  mano_obra REAL,
                  items TEXT,
                  total REAL,
                  estado TEXT,
                  notas TEXT)''')
    
    # Tabla de clientes
    c.execute('''CREATE TABLE IF NOT EXISTS clientes
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  nombre TEXT UNIQUE,
                  telefono TEXT,
                  email TEXT,
                  direccion TEXT,
                  fecha_registro TEXT)''')
    
    # Tabla de productos/servicios
    c.execute('''CREATE TABLE IF NOT EXISTS productos
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  nombre TEXT UNIQUE,
                  precio REAL,
                  tipo TEXT,
                  fecha_creacion TEXT)''')
    
    conn.commit()
    conn.close()

# ==================== FUNCIONES DE BASE DE DATOS ====================

def guardar_presupuesto(cliente_nombre, cliente_telefono, cliente_email, 
                        repuestos, mano_obra, items, total, notas=""):
    """Guardar presupuesto en la base de datos"""
    conn = sqlite3.connect('taller_presupuestos.db')
    c = conn.cursor()
    
    # Guardar cliente si no existe
    try:
        c.execute("INSERT OR IGNORE INTO clientes (nombre, telefono, email, fecha_registro) VALUES (?, ?, ?, ?)",
                  (cliente_nombre, cliente_telefono, cliente_email, datetime.now().isoformat()))
        conn.commit()
    except:
        pass
    
    # Guardar presupuesto
    items_json = json.dumps(items)
    c.execute('''INSERT INTO presupuestos 
                 (fecha, cliente_nombre, cliente_telefono, cliente_email, 
                  repuestos, mano_obra, items, total, estado, notas)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
              (datetime.now().isoformat(), cliente_nombre, cliente_telefono, 
               cliente_email, repuestos, mano_obra, items_json, total, 
               "PENDIENTE", notas))
    
    presupuesto_id = c.lastrowid
    conn.commit()
    conn.close()
    
    return presupuesto_id

def cargar_presupuestos():
    """Cargar historial de presupuestos"""
    conn = sqlite3.connect('taller_presupuestos.db')
    df = pd.read_sql_query("SELECT * FROM presupuestos ORDER BY fecha DESC", conn)
    conn.close()
    return df

def cargar_clientes():
    """Cargar lista de clientes"""
    conn = sqlite3.connect('taller_presupuestos.db')
    df = pd.read_sql_query("SELECT * FROM clientes ORDER BY nombre", conn)
    conn.close()
    return df

def actualizar_estado_presupuesto(presupuesto_id, nuevo_estado):
    """Actualizar estado de un presupuesto"""
    conn = sqlite3.connect('taller_presupuestos.db')
    c = conn.cursor()
    c.execute("UPDATE presupuestos SET estado = ? WHERE id = ?", 
              (nuevo_estado, presupuesto_id))
    conn.commit()
    conn.close()

# ==================== FUNCIONES DE PDF ====================

class PDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 16)
        self.cell(0, 10, 'TALLER MECÁNICO - PRESUPUESTO', 0, 1, 'C')
        self.set_font('Arial', '', 10)
        self.cell(0, 5, 'Documento válido como presupuesto', 0, 1, 'C')
        self.ln(10)
    
    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Página {self.page_no()}', 0, 0, 'C')

def generar_pdf(cliente_nombre, cliente_telefono, cliente_email, 
                repuestos, mano_obra, items, total, fecha):
    """Generar PDF del presupuesto"""
    pdf = PDF()
    pdf.add_page()
    
    # Datos del cliente
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, 'DATOS DEL CLIENTE', 0, 1)
    pdf.set_font('Arial', '', 10)
    pdf.cell(0, 5, f'Nombre: {cliente_nombre}', 0, 1)
    if cliente_telefono:
        pdf.cell(0, 5, f'Teléfono: {cliente_telefono}', 0, 1)
    if cliente_email:
        pdf.cell(0, 5, f'Email: {cliente_email}', 0, 1)
    pdf.cell(0, 5, f'Fecha: {fecha}', 0, 1)
    pdf.ln(5)
    
    # Detalles del presupuesto
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, 'DETALLES DEL PRESUPUESTO', 0, 1)
    
    # Tabla
    pdf.set_font('Arial', 'B', 10)
    pdf.cell(80, 8, 'Concepto', 1)
    pdf.cell(50, 8, 'Cantidad', 1)
    pdf.cell(50, 8, 'Subtotal', 1)
    pdf.ln()
    
    pdf.set_font('Arial', '', 10)
    pdf.cell(80, 8, 'Repuestos', 1)
    pdf.cell(50, 8, '1', 1)
    pdf.cell(50, 8, f'${repuestos:.2f}', 1)
    pdf.ln()
    
    pdf.cell(80, 8, 'Mano de obra', 1)
    pdf.cell(50, 8, '1', 1)
    pdf.cell(50, 8, f'${mano_obra:.2f}', 1)
    pdf.ln()
    
    for item in items:
        pdf.cell(80, 8, item['nombre'], 1)
        pdf.cell(50, 8, '1', 1)
        pdf.cell(50, 8, f'${item["precio"]:.2f}', 1)
        pdf.ln()
    
    # Total
    pdf.ln(5)
    pdf.set_font('Arial', 'B', 14)
    pdf.cell(130, 10, 'TOTAL:', 0)
    pdf.cell(50, 10, f'${total:.2f}', 0, 1, 'R')
    
    # Notas
    pdf.ln(10)
    pdf.set_font('Arial', 'I', 9)
    pdf.cell(0, 5, 'Presupuesto válido por 30 días.', 0, 1)
    pdf.cell(0, 5, 'Incluye garantía de 3 meses en mano de obra.', 0, 1)
    
    # Generar archivo
    output = io.BytesIO()
    pdf.output(output)
    return output.getvalue()

# ==================== FUNCIONES DE ESTADÍSTICAS ====================

def mostrar_estadisticas(df_presupuestos):
    """Mostrar estadísticas en el sidebar"""
    if not df_presupuestos.empty:
        st.sidebar.markdown("---")
        st.sidebar.subheader("📊 Estadísticas rápidas")
        
        total_presupuestos = len(df_presupuestos)
        total_facturado = df_presupuestos['total'].sum()
        promedio = df_presupuestos['total'].mean()
        
        st.sidebar.metric("Total presupuestos", total_presupuestos)
        st.sidebar.metric("Total facturado", f"${total_facturado:,.2f}")
        st.sidebar.metric("Promedio", f"${promedio:,.2f}")
        
        # Gráfico de tendencia
        if len(df_presupuestos) > 1:
            df_grafico = df_presupuestos.copy()
            df_grafico['fecha'] = pd.to_datetime(df_grafico['fecha'])
            df_grafico = df_grafico.sort_values('fecha')
            fig = px.line(df_grafico, x='fecha', y='total', 
                          title='Tendencia de presupuestos')
            st.sidebar.plotly_chart(fig, use_container_width=True)

# ==================== INTERFAZ PRINCIPAL ====================

def main():
    """Función principal de la aplicación"""
    
    # Inicializar base de datos
    init_database()
    
    # Inicializar session state
    if 'items' not in st.session_state:
        st.session_state.items = []
    if 'presupuesto_actual' not in st.session_state:
        st.session_state.presupuesto_actual = None
    
    # Sidebar - Navegación
    with st.sidebar:
        st.image("https://cdn-icons-png.flaticon.com/512/2917/2917995.png", width=50)
        st.title("🔧 Taller Pro")
        
        opcion = st.radio(
            "Menú principal",
            ["💰 Nuevo Presupuesto", "📋 Historial", "👥 Clientes", "📊 Estadísticas"],
            index=0
        )
        
        # Mostrar estadísticas en sidebar
        df_presupuestos = cargar_presupuestos()
        mostrar_estadisticas(df_presupuestos)
    
    # ==================== NUEVO PRESUPUESTO ====================
    if opcion == "💰 Nuevo Presupuesto":
        st.markdown('<div class="main-header"><h1>💰 Nuevo Presupuesto</h1><p>Complete los datos para generar un presupuesto profesional</p></div>', unsafe_allow_html=True)
        
        col1, col2 = st.columns(2)
        
        with col1:
            cliente_nombre = st.text_input("Nombre del cliente *", placeholder="Ej: Juan Pérez")
            cliente_telefono = st.text_input("Teléfono", placeholder="Ej: 123456789")
        
        with col2:
            cliente_email = st.text_input("Email", placeholder="cliente@email.com")
            notas = st.text_area("Notas adicionales", placeholder="Observaciones importantes...")
        
        st.markdown("---")
        
        # Costos principales
        col1, col2 = st.columns(2)
        with col1:
            repuestos = st.number_input("🔧 Costo de repuestos ($)", min_value=0.0, step=10.0, key="repuestos_main")
        with col2:
            mano_obra = st.number_input("👨‍🔧 Mano de obra ($)", min_value=0.0, step=10.0, key="mano_obra_main")
        
        st.markdown("---")
        
        # Items adicionales
        st.subheader("➕ Items adicionales")
        col_item1, col_item2, col_item3 = st.columns([3, 2, 1])
        
        with col_item1:
            nuevo_item = st.text_input("Nombre del ítem", key="nombre_item")
        with col_item2:
            precio_item = st.number_input("Precio", min_value=0.0, key="precio_item")
        with col_item3:
            if st.button("➕ Agregar", use_container_width=True):
                if nuevo_item and precio_item > 0:
                    st.session_state.items.append({"nombre": nuevo_item, "precio": precio_item})
                    st.success(f"✅ '{nuevo_item}' agregado!")
                    st.rerun()
        
        # Mostrar items agregados
        if st.session_state.items:
            st.subheader("📋 Items agregados:")
            for i, item in enumerate(st.session_state.items):
                col_a, col_b, col_c = st.columns([3, 2, 1])
                col_a.write(f"**{item['nombre']}**")
                col_b.write(f"${item['precio']:.2f}")
                if col_c.button("❌", key=f"del_{i}"):
                    st.session_state.items.pop(i)
                    st.rerun()
        
        st.markdown("---")
        
        # Calcular total
        total_items = sum(item['precio'] for item in st.session_state.items)
        total_general = repuestos + mano_obra + total_items
        
        # Mostrar resumen
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown('<div class="presupuesto-card">', unsafe_allow_html=True)
            st.subheader("📝 Resumen")
            st.write(f"**Repuestos:** ${repuestos:,.2f}")
            st.write(f"**Mano de obra:** ${mano_obra:,.2f}")
            st.write(f"**Items adicionales:** ${total_items:,.2f}")
            st.markdown('</div>', unsafe_allow_html=True)
        
        with col2:
            st.markdown('<div class="total-card">', unsafe_allow_html=True)
            st.subheader("💰 TOTAL")
            st.markdown(f"<h1 style='color:white;'>${total_general:,.2f}</h1>", unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)
        
        # Botones de acción
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("💾 Guardar Presupuesto", type="primary", use_container_width=True):
                if not cliente_nombre:
                    st.error("❌ Por favor ingrese el nombre del cliente")
                else:
                    presupuesto_id = guardar_presupuesto(
                        cliente_nombre, cliente_telefono, cliente_email,
                        repuestos, mano_obra, st.session_state.items, 
                        total_general, notas
                    )
                    st.session_state.presupuesto_actual = presupuesto_id
                    st.success(f"✅ Presupuesto guardado con ID: #{presupuesto_id}")
                    
                    # Limpiar items después de guardar
                    st.session_state.items = []
        
        with col2:
            if st.button("📄 Generar PDF", use_container_width=True):
                if cliente_nombre:
                    pdf_bytes = generar_pdf(
                        cliente_nombre, cliente_telefono, cliente_email,
                        repuestos, mano_obra, st.session_state.items, 
                        total_general, datetime.now().strftime("%d/%m/%Y %H:%M")
                    )
                    b64 = base64.b64encode(pdf_bytes).decode()
                    href = f'<a href="data:application/pdf;base64,{b64}" download="presupuesto_{cliente_nombre.replace(" ", "_")}.pdf">📥 Descargar PDF</a>'
                    st.markdown(href, unsafe_allow_html=True)
                    st.success("✅ PDF generado correctamente!")
                else:
                    st.error("❌ Complete el nombre del cliente primero")
        
        with col3:
            if st.button("🔄 Limpiar todo", use_container_width=True):
                st.session_state.items = []
                st.rerun()
    
    # ==================== HISTORIAL ====================
    elif opcion == "📋 Historial":
        st.markdown('<div class="main-header"><h1>📋 Historial de Presupuestos</h1></div>', unsafe_allow_html=True)
        
        df = cargar_presupuestos()
        
        if not df.empty:
            # Filtros
            col1, col2 = st.columns(2)
            with col1:
                estados = st.multiselect("Filtrar por estado", 
                                         ["PENDIENTE", "APROBADO", "RECHAZADO", "FACTURADO"],
                                         default=["PENDIENTE", "APROBADO", "FACTURADO"])
            with col2:
                busqueda = st.text_input("Buscar por cliente", placeholder="Nombre...")
            
            # Aplicar filtros
            if estados:
                df = df[df['estado'].isin(estados)]
            if busqueda:
                df = df[df['cliente_nombre'].str.contains(busqueda, case=False, na=False)]
            
            # Mostrar presupuestos
            for idx, row in df.head(20).iterrows():
                with st.expander(f"📄 Presupuesto #{row['id']} - {row['cliente_nombre']} - ${row['total']:,.2f} - {row['estado']}"):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.write(f"**Fecha:** {row['fecha'][:16]}")
                        st.write(f"**Cliente:** {row['cliente_nombre']}")
                        st.write(f"**Teléfono:** {row['cliente_telefono']}")
                        st.write(f"**Email:** {row['cliente_email']}")
                    
                    with col2:
                        st.write(f"**Repuestos:** ${row['repuestos']:.2f}")
                        st.write(f"**Mano de obra:** ${row['mano_obra']:.2f}")
                        items = json.loads(row['items'])
                        if items:
                            st.write("**Items extra:**")
                            for item in items:
                                st.write(f"  - {item['nombre']}: ${item['precio']:.2f}")
                    
                    # Cambiar estado
                    nuevo_estado = st.selectbox(
                        "Cambiar estado",
                        ["PENDIENTE", "APROBADO", "RECHAZADO", "FACTURADO"],
                        index=["PENDIENTE", "APROBADO", "RECHAZADO", "FACTURADO"].index(row['estado']),
                        key=f"estado_{row['id']}"
                    )
                    
                    if nuevo_estado != row['estado']:
                        actualizar_estado_presupuesto(row['id'], nuevo_estado)
                        st.rerun()
        else:
            st.info("📭 No hay presupuestos guardados aún")
    
    # ==================== CLIENTES ====================
    elif opcion == "👥 Clientes":
        st.markdown('<div class="main-header"><h1>👥 Gestión de Clientes</h1></div>', unsafe_allow_html=True)
        
        df_clientes = cargar_clientes()
        
        if not df_clientes.empty:
            st.dataframe(df_clientes[['nombre', 'telefono', 'email']], use_container_width=True)
            
            # Ver presupuestos del cliente
            cliente_seleccionado = st.selectbox("Ver presupuestos de cliente", df_clientes['nombre'].tolist())
            if cliente_seleccionado:
                df_presup = cargar_presupuestos()
                df_presup_cliente = df_presup[df_presup['cliente_nombre'] == cliente_seleccionado]
                if not df_presup_cliente.empty:
                    st.write(f"**Presupuestos de {cliente_seleccionado}:**")
                    for _, row in df_presup_cliente.iterrows():
                        st.write(f"- #{row['id']} - ${row['total']:.2f} - {row['estado']}")
                else:
                    st.info("Este cliente no tiene presupuestos aún")
        else:
            st.info("📭 No hay clientes registrados aún")
    
    # ==================== ESTADÍSTICAS ====================
    elif opcion == "📊 Estadísticas":
        st.markdown('<div class="main-header"><h1>📊 Estadísticas y Reportes</h1></div>', unsafe_allow_html=True)
        
        df = cargar_presupuestos()
        
        if not df.empty:
            col1, col2 = st.columns(2)
            
            with col1:
                # Gráfico de presupuestos por estado
                estados_counts = df['estado'].value_counts()
                fig1 = px.pie(values=estados_counts.values, names=estados_counts.index, 
                              title="Distribución por Estado")
                st.plotly_chart(fig1, use_container_width=True)
            
            with col2:
                # Top clientes
                top_clientes = df.groupby('cliente_nombre')['total'].sum().nlargest(5)
                fig2 = px.bar(x=top_clientes.values, y=top_clientes.index, 
                              orientation='h', title="Top 5 Clientes por Facturación")
                st.plotly_chart(fig2, use_container_width=True)
            
            # Tendencia temporal
            df_tendencia = df.copy()
            df_tendencia['fecha'] = pd.to_datetime(df_tendencia['fecha']).dt.date
            tendencia = df_tendencia.groupby('fecha')['total'].sum().reset_index()
            fig3 = px.line(tendencia, x='fecha', y='total', 
                           title="Evolución de Presupuestos")
            st.plotly_chart(fig3, use_container_width=True)
            
            # Exportar datos
            st.markdown("---")
            st.subheader("📥 Exportar Datos")
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button("Descargar CSV", csv, "presupuestos.csv", "text/csv")
        else:
            st.info("📊 No hay datos suficientes para mostrar estadísticas")

if __name__ == "__main__":
    main()
