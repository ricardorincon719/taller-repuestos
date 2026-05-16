import streamlit as st
from datetime import datetime, timedelta
import json
import os
import bcrypt
import secrets
import shutil
from pathlib import Path
from streamlit_cookies_manager import EncryptedCookieManager
from dotenv import load_dotenv
from filelock import FileLock, Timeout

# Load environment variables from .env in development
load_dotenv()

# --- REQUIRED ENVIRONMENT VARIABLES ---
REQUIRED_ENVS = ["ADMIN_PASSWORD", "MASTER_ACTIVATION_KEY", "COOKIE_PASSWORD"]
missing_envs = [v for v in REQUIRED_ENVS if not os.environ.get(v)]
if missing_envs:
    raise RuntimeError(
        "Missing required environment variables: " + ", ".join(missing_envs) + 
        ". Define them in the environment or in a .env file (see .env.example)."
    )

ADMIN_PASSWORD = os.environ["ADMIN_PASSWORD"]
MASTER_ACTIVATION_KEY = os.environ["MASTER_ACTIVATION_KEY"]
COOKIE_PASSWORD = os.environ["COOKIE_PASSWORD"]

# --- CONFIGURACIÓN PROFESIONAL ---
st.set_page_config(page_title="Taller Pro", page_icon="🔧", layout="wide")

# --- SISTEMA DE RESPALDO AUTOMÁTICO ---
def backup_datos():
    """Crea respaldo automático cada 10 ejecuciones"""
    if 'backup_counter' not in st.session_state:
        st.session_state.backup_counter = 0
    
    st.session_state.backup_counter += 1
    if st.session_state.backup_counter % 10 == 0:
        backup_dir = Path("backups")
        backup_dir.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        if os.path.exists(USUARIOS_FILE):
            try:
                shutil.copy(USUARIOS_FILE, backup_dir / f"usuarios_{timestamp}.json")
            except Exception as e:
                st.error(f"Error creando backup usuarios: {e}")
        if os.path.exists(PRESUPUESTOS_FILE):
            try:
                shutil.copy(PRESUPUESTOS_FILE, backup_dir / f"presupuestos_{timestamp}.json")
            except Exception as e:
                st.error(f"Error creando backup presupuestos: {e}")

# --- GESTIÓN DE COOKIES ---
cookies = EncryptedCookieManager(
    prefix="taller_pro_",
    password=COOKIE_PASSWORD
)
if not cookies.ready():
    st.stop()

# --- RUTAS DE DATOS ---
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

USUARIOS_FILE = DATA_DIR / "usuarios.json"
PRESUPUESTOS_FILE = DATA_DIR / "presupuestos.json"
CONFIG_FILE = DATA_DIR / "config.json"

# --- FUNCIONES DE PERSISTENCIA ---
def cargar_json(archivo, default=None):
    try:
        if os.path.exists(archivo):
            # Use a short lock for reading to avoid race conditions with writers
            lock_path = str(archivo) + ".lock"
            lock = FileLock(lock_path, timeout=2)
            try:
                with lock:
                    with open(archivo, 'r', encoding='utf-8') as f:
                        return json.load(f)
            except Timeout:
                st.error("El archivo está siendo usado por otro proceso. Intenta de nuevo.")
                return default if default is not None else {}
    except Exception as e:
        st.error(f"Error cargando datos: {e}")
    return default if default is not None else {}


def guardar_json(archivo, datos):
    temp_file = archivo.with_suffix('.tmp')
    lock_path = str(archivo) + ".lock"
    lock = FileLock(lock_path, timeout=5)
    try:
        with lock:
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(datos, f, indent=2, ensure_ascii=False)
            temp_file.replace(archivo)
        return True
    except Timeout:
        st.error("Otro proceso está usando el archivo, inténtalo de nuevo.")
        return False
    except Exception as e:
        st.error(f"Error guardando: {e}")
        return False


def cargar_usuarios():
    return cargar_json(USUARIOS_FILE, {})

def guardar_usuarios(usuarios):
    return guardar_json(USUARIOS_FILE, usuarios)

def cargar_presupuestos():
    return cargar_json(PRESUPUESTOS_FILE, [])

def guardar_presupuestos(presupuestos):
    return guardar_json(PRESUPUESTOS_FILE, presupuestos)

def cargar_config():
    default_config = {
        "dias_prueba": 7,
        "admin_email": "admin@tallerpro.com",
        "version": "2.0.0"
    }
    return cargar_json(CONFIG_FILE, default_config)

config = cargar_config()

# --- INICIALIZACIÓN DEL ESTADO ---
if 'presupuestos' not in st.session_state:
    st.session_state.presupuestos = cargar_presupuestos()
if 'items_actuales' not in st.session_state:
    st.session_state.items_actuales = []
if 'autenticado' not in st.session_state:
    st.session_state.autenticado = False
if 'usuario_email' not in st.session_state:
    st.session_state.usuario_email = None

# Verificar cookie al iniciar
if not st.session_state.autenticado and cookies.get("logged_in_email"):
    email_cookie = cookies.get("logged_in_email")
    usuarios = cargar_usuarios()
    if email_cookie in usuarios:
        st.session_state.autenticado = True
        st.session_state.usuario_email = email_cookie
        st.session_state.usuario_data = usuarios[email_cookie]

backup_datos()

# --- FUNCIONES DE SEGURIDAD ---
def hash_password(password):
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def check_password(password, hashed):
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

def generar_codigo_activacion(email):
    return f"TP-{secrets.token_hex(4).upper()[:8]}"


def verificar_licencia(usuario_data):
    estado = usuario_data.get('estado', 'prueba')
    if estado == 'activo':
        return True, 0, 'activo'
    
    fecha_reg = datetime.strptime(usuario_data['fecha_registro'], "%Y-%m-%d")
    dias_transcurridos = (datetime.now() - fecha_reg).days
    dias_restantes = config['dias_prueba'] - dias_transcurridos
    
    if dias_restantes > 0:
        return True, dias_restantes, 'prueba'
    else:
        usuario_data['estado'] = 'expirado'
        usuarios = cargar_usuarios()
        usuarios[usuario_data['email']] = usuario_data
        guardar_usuarios(usuarios)
        return False, 0, 'expirado'

# =============================================
# INTERFAZ DE LOGIN/REGISTRO
# =============================================
if not st.session_state.autenticado:
    st.title("🔧 Taller Pro - Sistema de Presupuestos")
    st.markdown("---")
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.markdown("### 🔐 Acceso Clientes")
        with st.form("login_form", clear_on_submit=False):
            email_login = st.text_input("📧 Email")
            password_login = st.text_input("🔑 Contraseña", type="password")
            login_btn = st.form_submit_button("🚀 Ingresar", use_container_width=True)
            
            if login_btn:
                usuarios = cargar_usuarios()
                if email_login in usuarios:
                    if check_password(password_login, usuarios[email_login]['password']):
                        acceso, dias, estado = verificar_licencia(usuarios[email_login])
                        if acceso:
                            st.session_state.autenticado = True
                            st.session_state.usuario_email = email_login
                            st.session_state.usuario_data = usuarios[email_login]
                            cookies["logged_in_email"] = email_login
                            cookies.save()
                            st.success("✅ Acceso autorizado")
                            st.rerun()
                        else:
                            st.session_state.temp_email = email_login
                            st.error("⏰ Licencia expirada - Requiere activación")
                            st.rerun()
                    else:
                        st.error("❌ Credenciales inválidas")
                else:
                    st.error("❌ Usuario no registrado")
    
    with col2:
        st.markdown("### 📝 Nueva Cuenta")
        st.info(f"✨ **{config['dias_prueba']} días de prueba GRATIS**")
        
        with st.form("registro_form", clear_on_submit=True):
            email_reg = st.text_input("📧 Email", key="reg_email")
            nombre_empresa = st.text_input("🏢 Empresa (opcional)")
            password_reg = st.text_input("🔑 Contraseña", type="password", key="reg_pass")
            password_conf = st.text_input("✓ Confirmar Contraseña", type="password")
            
            registro_btn = st.form_submit_button("🎯 Comenzar Prueba Gratis", use_container_width=True)
            
            if registro_btn:
                if password_reg != password_conf:
                    st.error("❌ Las contraseñas no coinciden")
                elif len(password_reg) < 6:
                    st.error("❌ Contraseña muy corta (mínimo 6)")
                else:
                    usuarios = cargar_usuarios()
                    if email_reg in usuarios:
                        st.error("❌ Email ya registrado")
                    else:
                        nuevo_usuario = {
                            "email": email_reg,
                            "nombre_empresa": nombre_empresa,
                            "password": hash_password(password_reg),
                            "fecha_registro": datetime.now().strftime("%Y-%m-%d"),
                            "fecha_activacion": None,
                            "estado": "prueba",
                            "codigo_activacion": None,
                            "plan": "trial",
                            "presupuestos_creados": 0
                        }
                        usuarios[email_reg] = nuevo_usuario
                        guardar_usuarios(usuarios)
                        
                        st.session_state.autenticado = True
                        st.session_state.usuario_email = email_reg
                        st.session_state.usuario_data = nuevo_usuario
                        cookies["logged_in_email"] = email_reg
                        cookies.save()
                        st.success("✅ ¡Bienvenido! Disfruta tu prueba gratis")
                        st.balloons()
                        st.rerun()
    
    # Pantalla de activación
    if 'temp_email' in st.session_state:
        st.markdown("---")
        st.markdown("## 💳 Activación de Licencia")
        
        with st.form("activacion_form"):
            codigo = st.text_input("🔑 Código de Activación", placeholder="Ej: TP-A1B2C3D4")
            if st.form_submit_button("✨ Activar Ahora", use_container_width=True):
                email_act = st.session_state.temp_email
                usuarios = cargar_usuarios()
                
                if email_act in usuarios:
                    codigo_guardado = usuarios[email_act].get('codigo_activacion')
                    if codigo == codigo_guardado or codigo == MASTER_ACTIVATION_KEY:
                        usuarios[email_act]['estado'] = 'activo'
                        usuarios[email_act]['fecha_activacion'] = datetime.now().strftime("%Y-%m-%d")
                        usuarios[email_act]['plan'] = 'profesional'
                        guardar_usuarios(usuarios)
                        del st.session_state.temp_email
                        st.success("✅ ¡Licencia Activada! Redirigiendo...")
                        st.rerun()
                    else:
                        st.error("❌ Código inválido")
        st.stop()

# =============================================
# APLICACIÓN PRINCIPAL (USUARIOS AUTENTICADOS)
# =============================================
else:
    # Verificar licencia
    usuarios = cargar_usuarios()
    usuario_actual = usuarios.get(st.session_state.usuario_email, st.session_state.usuario_data)
    acceso, dias_restantes, estado_lic = verificar_licencia(usuario_actual)
    
    if not acceso:
        st.warning("⏰ **Licencia Expirada**")
        
        col1, col2 = st.columns([2, 1])
        with col1:
            codigo_act = st.text_input("🔑 Código de Activación", placeholder="Ingresa el código recibido")
        with col2:
            if st.button("Activar Licencia", use_container_width=True):
                if codigo_act == usuario_actual.get('codigo_activacion') or codigo_act == MASTER_ACTIVATION_KEY:
                    usuario_actual['estado'] = 'activo'
                    guardar_usuarios(usuarios)
                    st.success("✅ Licencia activada")
                    st.rerun()
                else:
                    st.error("❌ Código incorrecto")
        st.stop()
    
    # --- HEADER ---
    st.title(f"🔧 Taller Pro - {usuario_actual.get('nombre_empresa', 'Profesional')}")
    
    # --- SIDEBAR ---
    with st.sidebar:
        st.markdown(f"### 👤 {st.session_state.usuario_email}")
        
        # Estado de licencia
        if estado_lic == 'prueba':
            progreso = max(0, min(1, dias_restantes / config['dias_prueba']))
            st.progress(progreso, text=f"⏳ Prueba: {dias_restantes} días")
        else:
            st.success("✅ **Licencia Activa**")
        
        st.markdown("---")
        
        # Métricas con lógica CORRECTA
        mis_presupuestos = [p for p in st.session_state.presupuestos 
                          if p.get('usuario_creador') == st.session_state.usuario_email]
        
        # Solo FACTURADOS cuentan como facturación real
        facturados = [p for p in mis_presupuestos if p.get('estado') == 'FACTURADO']
        pendientes = [p for p in mis_presupuestos if p.get('estado') == 'PENDIENTE']
        aprobados = [p for p in mis_presupuestos if p.get('estado') == 'APROBADO']
        
        total_mis_presupuestos = len(mis_presupuestos)
        total_facturado_real = sum(p.get('total', 0) for p in facturados)
        total_pendiente = sum(p.get('total', 0) for p in pendientes)
        total_aprobado = sum(p.get('total', 0) for p in aprobados)
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("📄 Presupuestos", total_mis_presupuestos)
        with col2:
            st.metric("💰 Facturado", f"${total_facturado_real:,.0f}")
        
        # Mostrar pendiente por cobrar
        if total_pendiente > 0:
            st.caption(f"⏳ Pendiente: ${total_pendiente:,.2f}")
        if total_aprobado > 0:
            st.caption(f"✅ Aprobado (sin facturar): ${total_aprobado:,.2f}")
        
        st.markdown("---")
        
        # Exportar datos
        if st.button("📥 Exportar Mis Datos", use_container_width=True):
            datos_export = {
                "usuario": usuario_actual['email'],
                "fecha_exportacion": datetime.now().isoformat(),
                "presupuestos": mis_presupuestos,
                "resumen": {
                    "total_presupuestos": total_mis_presupuestos,
                    "total_facturado": total_facturado_real,
                    "total_pendiente": total_pendiente,
                    "total_aprobado": total_aprobado
                }
            }
            st.download_button(
                "⬇️ Descargar JSON",
                json.dumps(datos_export, indent=2, ensure_ascii=False),
                f"taller_pro_{datetime.now():%Y%m%d}.json",
                "application/json",
                use_container_width=True
            )
        
        # Cerrar sesión
        if st.button("🚪 Cerrar Sesión", use_container_width=True):
            st.session_state.autenticado = False
            st.session_state.usuario_email = None
            cookies["logged_in_email"] = ""
            cookies.save()
            st.rerun()
        
        st.markdown("---")
        
        # =============================================
        # PANEL ADMIN COMPLETO
        # =============================================
        with st.expander("⚙️ Panel Admin", expanded=False):
            admin_password = st.text_input("🔐 Clave Administrador", type="password", key="admin_pass")
            
            if admin_password == ADMIN_PASSWORD:
                st.success("✅ **Acceso Administrativo Autorizado**")
                st.markdown("---")
                
                # Pestañas del panel admin
                admin_tab1, admin_tab2, admin_tab3 = st.tabs([
                    "👥 Usuarios", "📊 Estadísticas Globales", "⚡ Acciones Rápidas"
                ])
                
                # --- TAB 1: GESTIÓN DE USUARIOS ---
                with admin_tab1:
                    st.markdown("### 👥 Gestión de Usuarios")
                    
                    todos_usuarios = cargar_usuarios()
                    
                    # Filtro por estado
                    filtro_estado = st.selectbox(
                        "Filtrar por estado",
                        ["TODOS", "prueba", "activo", "expirado", "bloqueado"]
                    )
                    
                    for email, data in todos_usuarios.items():
                        # Aplicar filtro
                        if filtro_estado != "TODOS" and data.get('estado') != filtro_estado:
                            continue
                        
                        with st.container():
                            # Cabecera del usuario
                            col1, col2, col3 = st.columns([2, 1, 1])
                            with col1:
                                st.markdown(f"**📧 {email}**")
                                if data.get('nombre_empresa'):
                                    st.caption(f"🏢 {data['nombre_empresa']}")
                            
                            # Estado con color
                            estado = data.get('estado', 'prueba')
                            if estado == 'activo':
                                with col2:
                                    st.success("✅ Activo")
                            elif estado == 'prueba':
                                fecha_reg = datetime.strptime(data['fecha_registro'], "%Y-%m-%d")
                                dias_transcurridos = (datetime.now() - fecha_reg).days
                                dias_rest = config['dias_prueba'] - dias_transcurridos
                                with col2:
                                    st.warning(f"⏳ Prueba ({max(0, dias_rest)}d)")
                            elif estado == 'expirado':
                                with col2:
                                    st.error("⏰ Expirado")
                            else:
                                with col2:
                                    st.info(f"📌 {estado}")
                            
                            with col3:
                                st.caption(f"📅 {data.get('fecha_registro', 'N/A')}")
                            
                            # Información adicional
                            col1, col2, col3, col4 = st.columns(4)
                            with col1:
                                st.metric("📄 Presupuestos", data.get('presupuestos_creados', 0))
                            with col2:
                                plan = data.get('plan', 'trial')
                                st.caption(f"💳 Plan: {plan}")
                            
                            # Botones de acción
                            col1, col2, col3, col4 = st.columns(4)
                            
                            with col1:
                                # BOTÓN PRINCIPAL: Activar licencia directamente
                                if estado != 'activo':
                                    if st.button("✅ **ACTIVAR**", 
                                               key=f"activar_directo_{email}",
                                               use_container_width=True,
                                               type="primary"):
                                        data['estado'] = 'activo'
                                        data['fecha_activacion'] = datetime.now().strftime("%Y-%m-%d")
                                        data['plan'] = 'profesional'
                                        guardar_usuarios(todos_usuarios)
                                        st.success(f"✅ ¡Licencia de {email} ACTIVADA!")
                                        st.balloons()
                                        st.rerun()
                            
                            with col2:
                                # Generar código de activación
                                if st.button("🔑 Código", key=f"gen_cod_{email}", use_container_width=True):
                                    codigo = generar_codigo_activacion(email)
                                    data['codigo_activacion'] = codigo
                                    guardar_usuarios(todos_usuarios)
                                    st.success(f"Código: **{codigo}**")
                            
                            with col3:
                                # Extender prueba
                                if estado == 'prueba':
                                    if st.button("⏰ +7d", key=f"extender_{email}", use_container_width=True):
                                        fecha_actual = datetime.strptime(data['fecha_registro'], "%Y-%m-%d")
                                        nueva_fecha = fecha_actual + timedelta(days=7)
                                        data['fecha_registro'] = nueva_fecha.strftime("%Y-%m-%d")
                                        guardar_usuarios(todos_usuarios)
                                        st.success(f"✅ +7 días para {email}")
                                        st.rerun()
                            
                            with col4:
                                # Bloquear usuario
                                if estado != 'bloqueado':
                                    if st.button("🚫 Bloq", key=f"bloq_{email}", use_container_width=True):
                                        data['estado'] = 'bloqueado'
                                        guardar_usuarios(todos_usuarios)
                                        st.warning(f"⛔ {email} bloqueado")
                                        st.rerun()
                                else:
                                    if st.button("🔓 Desbloq", key=f"desbloq_{email}", use_container_width=True):
                                        data['estado'] = 'prueba'
                                        guardar_usuarios(todos_usuarios)
                                        st.success(f"✅ {email} desbloqueado")
                                        st.rerun()
                            
                            # Mostrar código de activación si existe
                            if data.get('codigo_activacion'):
                                st.code(f"🎫 {data['codigo_activacion']}")
                            
                            st.divider()
                
                # --- TAB 2: ESTADÍSTICAS GLOBALES ---
                with admin_tab2:
                    st.markdown("### 📊 Estadísticas Globales del Sistema")
                    
                    todos_usuarios = cargar_usuarios()
                    todos_presupuestos = cargar_presupuestos()
                    
                    # Métricas globales
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("👥 Total Usuarios", len(todos_usuarios))
                    with col2:
                        usuarios_activos = sum(1 for u in todos_usuarios.values() if u.get('estado') == 'activo')
                        st.metric("✅ Activos", usuarios_activos)
                    with col3:
                        usuarios_prueba = sum(1 for u in todos_usuarios.values() if u.get('estado') == 'prueba')
                        st.metric("⏳ En Prueba", usuarios_prueba)
                    with col4:
                        st.metric("📄 Total Presupuestos", len(todos_presupuestos))
                    
                    st.markdown("---")
                    
                    # Facturación total (SOLO FACTURADOS)
                    facturacion_total = sum(
                        p.get('total', 0) for p in todos_presupuestos 
                        if p.get('estado') == 'FACTURADO'
                    )
                    st.metric("💰 Facturación Global Real", f"${facturacion_total:,.2f}")
                    
                    # Pendiente global
                    pendiente_global = sum(
                        p.get('total', 0) for p in todos_presupuestos 
                        if p.get('estado') in ['PENDIENTE', 'APROBADO']
                    )
                    st.caption(f"⏳ Pendiente por facturar: ${pendiente_global:,.2f}")
                    
                    st.markdown("---")
                    
                    # Top usuarios por facturación REAL
                    st.subheader("🏆 Top Usuarios por Facturación Real")
                    usuarios_facturacion = {}
                    for p in todos_presupuestos:
                        if p.get('estado') == 'FACTURADO':
                            usuario = p.get('usuario_creador', 'Desconocido')
                            usuarios_facturacion[usuario] = usuarios_facturacion.get(usuario, 0) + p.get('total', 0)
                    
                    top_usuarios = sorted(usuarios_facturacion.items(), key=lambda x: x[1], reverse=True)[:10]
                    if top_usuarios:
                        for i, (email, total) in enumerate(top_usuarios, 1):
                            st.write(f"**{i}. {email}:** ${total:,.2f}")
                    else:
                        st.info("No hay facturación registrada aún")
                    
                    st.markdown("---")
                    
                    # Distribución de estados
                    st.subheader("📊 Distribución de Estados")
                    estados_dist = {
                        "Activos": usuarios_activos,
                        "Prueba": usuarios_prueba,
                        "Expirados": sum(1 for u in todos_usuarios.values() if u.get('estado') == 'expirado'),
                        "Bloqueados": sum(1 for u in todos_usuarios.values() if u.get('estado') == 'bloqueado')
                    }
                    
                    for estado, count in estados_dist.items():
                        if count > 0:
                            porcentaje = (count / len(todos_usuarios)) * 100
                            st.write(f"**{estado}:** {count} usuarios")
                            st.progress(porcentaje / 100)
                
                # --- TAB 3: ACCIONES RÁPIDAS ---
                with admin_tab3:
                    st.markdown("### ⚡ Acciones Rápidas")
                    
                    if st.button("✅ ACTIVAR TODOS LOS USUARIOS EN PRUEBA", use_container_width=True, type="primary"):
                        todos_usuarios = cargar_usuarios()
                        activados = 0
                        for email, data in todos_usuarios.items():
                            if data.get('estado') == 'prueba':
                                data['estado'] = 'activo'
                                data['fecha_activacion'] = datetime.now().strftime("%Y-%m-%d")
                                data['plan'] = 'profesional'
                                activados += 1
                        guardar_usuarios(todos_usuarios)
                        st.success(f"✅ {activados} usuarios activados")
                        st.balloons()
                        st.rerun()
                    
                    if st.button("⏰ EXTENDER PRUEBA +7 DÍAS A TODOS", use_container_width=True):
                        todos_usuarios = cargar_usuarios()
                        extendidos = 0
                        for email, data in todos_usuarios.items():
                            if data.get('estado') == 'prueba':
                                fecha_actual = datetime.strptime(data['fecha_registro'], "%Y-%m-%d")
                                nueva_fecha = fecha_actual + timedelta(days=7)
                                data['fecha_registro'] = nueva_fecha.strftime("%Y-%m-%d")
                                extendidos += 1
                        guardar_usuarios(todos_usuarios)
                        st.success(f"✅ Prueba extendida para {extendidos} usuarios")
                        st.rerun()
                    
                    st.markdown("---")
                    
                    if st.button("💾 CREAR BACKUP MANUAL AHORA", use_container_width=True):
                        backup_dir = Path("backups")
                        backup_dir.mkdir(exist_ok=True)
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        
                        if os.path.exists(USUARIOS_FILE):
                            try:
                                shutil.copy(USUARIOS_FILE, backup_dir / f"usuarios_backup_{timestamp}.json")
                            except Exception as e:
                                st.error(f"Error al crear backup usuarios: {e}")
                        if os.path.exists(PRESUPUESTOS_FILE):
                            try:
                                shutil.copy(PRESUPUESTOS_FILE, backup_dir / f"presupuestos_backup_{timestamp}.json")
                            except Exception as e:
                                st.error(f"Error al crear backup presupuestos: {e}")
                        
                        st.success(f"✅ Backup creado: {timestamp}")
                    
                    st.markdown("---")
                    
                    st.subheader("ℹ️ Información del Sistema")
                    tamaño_datos = "0 KB"
                    if os.path.exists(USUARIOS_FILE):
                        tamaño_datos = f"{os.path.getsize(USUARIOS_FILE) / 1024:.2f} KB"
                    
                    st.json({
                        "version": config.get('version', '2.0.0'),
                        "dias_prueba": config['dias_prueba'],
                        "total_usuarios": len(cargar_usuarios()),
                        "total_presupuestos": len(cargar_presupuestos()),
                        "tamaño_datos": tamaño_datos,
                        "fecha_sistema": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    })
            
            elif admin_password and admin_password != ADMIN_PASSWORD:
                st.error("❌ Clave incorrecta")
    
    # =============================================
    # PESTAÑAS PRINCIPALES
    # =============================================
    tab1, tab2, tab3 = st.tabs(["💰 Nuevo Presupuesto", "📋 Historial", "📊 Estadísticas"])
    
    # --- TAB 1: NUEVO PRESUPUESTO ---
    with tab1:
        st.subheader("📝 Datos del cliente")
        
        col1, col2 = st.columns(2)
        with col1:
            cliente_nombre = st.text_input("Nombre del cliente *", placeholder="Ej: Juan Pérez")
            telefono = st.text_input("Teléfono", placeholder="Ej: 123456789")
        with col2:
            email_cliente = st.text_input("Email", placeholder="cliente@email.com")
            notas = st.text_area("Notas adicionales", placeholder="Observaciones...")
        
        st.markdown("---")
        
        col1, col2 = st.columns(2)
        with col1:
            repuestos = st.number_input("🔧 Repuestos ($)", min_value=0.0, step=10.0, value=0.0)
        with col2:
            mano_obra = st.number_input("👨‍🔧 Mano de obra ($)", min_value=0.0, step=10.0, value=0.0)
        
        st.markdown("---")
        
        st.subheader("➕ Items adicionales")
        col_a, col_b, col_c = st.columns([3, 2, 1])
        with col_a:
            item_nombre = st.text_input("Nombre del ítem", key="nuevo_item_nombre")
        with col_b:
            item_precio = st.number_input("Precio", min_value=0.0, key="nuevo_item_precio")
        with col_c:
            if st.button("➕ Agregar", key="btn_agregar_item", use_container_width=True):
                if item_nombre and item_precio > 0:
                    st.session_state.items_actuales.append({
                        "nombre": item_nombre,
                        "precio": item_precio
                    })
                    st.success(f"✅ '{item_nombre}' agregado")
                    st.rerun()
        
        if st.session_state.items_actuales:
            st.write("**Items agregados:**")
            for i, item in enumerate(st.session_state.items_actuales):
                col_a, col_b, col_c = st.columns([3, 2, 1])
                col_a.write(f"• {item['nombre']}")
                col_b.write(f"${item['precio']:.2f}")
                if col_c.button("❌", key=f"del_item_{i}"):
                    st.session_state.items_actuales.pop(i)
                    st.rerun()
        
        total_items = sum(i['precio'] for i in st.session_state.items_actuales)
        total_general = repuestos + mano_obra + total_items
        
        st.markdown("---")
        st.markdown(f"### 💰 TOTAL DEL PRESUPUESTO: **${total_general:,.2f}**")
        
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
                        "email": email_cliente,
                        "repuestos": repuestos,
                        "mano_obra": mano_obra,
                        "items": st.session_state.items_actuales.copy(),
                        "total": total_general,
                        "notas": notas,
                        "estado": "PENDIENTE",
                        "usuario_creador": st.session_state.usuario_email
                    }
                    st.session_state.presupuestos.append(nuevo_presupuesto)
                    guardar_presupuestos(st.session_state.presupuestos)
                    
                    usuario_actual['presupuestos_creados'] = usuario_actual.get('presupuestos_creados', 0) + 1
                    usuarios = cargar_usuarios()
                    usuarios[st.session_state.usuario_email] = usuario_actual
                    guardar_usuarios(usuarios)
                    
                    st.session_state.items_actuales = []
                    st.balloons()
                    st.success(f"✅ Presupuesto #{nuevo_id} guardado correctamente!")
                    st.rerun()
    
    # --- TAB 2: HISTORIAL ---
    with tab2:
        mis_presupuestos = [p for p in st.session_state.presupuestos 
                          if p.get('usuario_creador') == st.session_state.usuario_email]
        
        if not mis_presupuestos:
            st.info("📭 No hay presupuestos guardados aún.")
        else:
            busqueda = st.text_input("🔍 Buscar por cliente", placeholder="Nombre...")
            
            presupuestos_filtrados = mis_presupuestos
            if busqueda:
                presupuestos_filtrados = [p for p in presupuestos_filtrados 
                                        if busqueda.lower() in p['cliente'].lower()]
            
            st.write(f"**Mostrando {len(presupuestos_filtrados)} de {len(mis_presupuestos)} presupuestos**")
            
            for p in reversed(presupuestos_filtrados):
                estado_icono = {
                    "PENDIENTE": "🟡",
                    "APROBADO": "🟢",
                    "FACTURADO": "💰",
                    "RECHAZADO": "🔴"
                }.get(p['estado'], "📄")
                
                with st.expander(f"{estado_icono} #{p['id']} - {p['cliente']} - ${p['total']:,.2f} - {p['estado']}"):
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
                    
                    estados = ["PENDIENTE", "APROBADO", "FACTURADO", "RECHAZADO"]
                    estado_actual_idx = estados.index(p['estado']) if p['estado'] in estados else 0
                    nuevo_estado = st.selectbox(
                        "Cambiar estado",
                        estados,
                        index=estado_actual_idx,
                        key=f"estado_{p['id']}"
                    )
                    if nuevo_estado != p['estado']:
                        p['estado'] = nuevo_estado
                        guardar_presupuestos(st.session_state.presupuestos)
                        st.success(f"✅ Estado actualizado a {nuevo_estado}")
                        st.rerun()
    
    # --- TAB 3: ESTADÍSTICAS (LÓGICA CORRECTA) ---
    with tab3:
        mis_presupuestos = [p for p in st.session_state.presupuestos 
                          if p.get('usuario_creador') == st.session_state.usuario_email]
        
        if not mis_presupuestos:
            st.info("📊 No hay datos suficientes para mostrar estadísticas.")
        else:
            st.subheader("📈 Resumen de Facturación Real")
            
            # Separar por estados
            facturados = [p for p in mis_presupuestos if p.get('estado') == 'FACTURADO']
            aprobados = [p for p in mis_presupuestos if p.get('estado') == 'APROBADO']
            pendientes = [p for p in mis_presupuestos if p.get('estado') == 'PENDIENTE']
            rechazados = [p for p in mis_presupuestos if p.get('estado') == 'RECHAZADO']
            
            total_facturado = sum(p['total'] for p in facturados)
            total_aprobado = sum(p['total'] for p in aprobados)
            total_pendiente = sum(p['total'] for p in pendientes)
            total_rechazado = sum(p['total'] for p in rechazados)
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("📄 Total", len(mis_presupuestos))
            with col2:
                st.metric("💰 Facturado", f"${total_facturado:,.2f}")
            with col3:
                st.metric("✅ Aprobado", f"${total_aprobado:,.2f}")
            with col4:
                st.metric("⏳ Pendiente", f"${total_pendiente:,.2f}")
            
            st.markdown("---")
            
            # Promedio solo de facturados
            if facturados:
                promedio = total_facturado / len(facturados)
                st.metric("📊 Promedio por factura", f"${promedio:,.2f}")
            
            st.markdown("---")
            
            # Distribución por estado
            st.subheader("📊 Distribución por estado")
            estados_count = {
                "FACTURADO": len(facturados),
                "APROBADO": len(aprobados),
                "PENDIENTE": len(pendientes),
                "RECHAZADO": len(rechazados)
            }
            
            for estado, count in estados_count.items():
                if count > 0:
                    porcentaje = (count / len(mis_presupuestos)) * 100
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.write(f"**{estado}:** {count} presupuestos")
                        st.progress(porcentaje / 100)
                    with col2:
                        st.write(f"{porcentaje:.1f}%")
            
            st.markdown("---")
            
            # Top clientes (solo facturados)
            st.subheader("🏆 Top 5 clientes facturados")
            clientes_facturado = {}
            for p in facturados:
                cliente = p['cliente']
                clientes_facturado[cliente] = clientes_facturado.get(cliente, 0) + p['total']
            
            top_clientes = sorted(clientes_facturado.items(), key=lambda x: x[1], reverse=True)[:5]
            
            if top_clientes:
                for i, (cliente, total_cliente) in enumerate(top_clientes, 1):
                    st.write(f"**{i}. {cliente}:** ${total_cliente:,.2f}")
            else:
                st.info("No hay facturación registrada aún")
            
            st.markdown("---")
            
            # Facturación mensual (solo facturados)
            st.subheader("📅 Facturación mensual real")
            facturacion_mensual = {}
            for p in facturados:
                fecha = datetime.strptime(p['fecha'], "%Y-%m-%d %H:%M")
                mes_key = fecha.strftime("%Y-%m")
                facturacion_mensual[mes_key] = facturacion_mensual.get(mes_key, 0) + p['total']
            
            if facturacion_mensual:
                meses_ordenados = sorted(facturacion_mensual.items())
                max_fact = max(facturacion_mensual.values()) if facturacion_mensual else 1
                for mes, monto in meses_ordenados:
                    porcentaje = (monto / max_fact) * 100
                    st.write(f"**{mes}:** ${monto:,.2f}")
                    st.progress(porcentaje / 100)
            else:
                st.info("No hay facturación mensual registrada")
            
            st.markdown("---")
            
            # Items más facturados
            st.subheader("🔧 Items más facturados")
            items_count = {}
            for p in facturados:
                for item in p.get('items', []):
                    nombre = item['nombre']
                    items_count[nombre] = items_count.get(nombre, 0) + 1
            
            if items_count:
                top_items = sorted(items_count.items(), key=lambda x: x[1], reverse=True)[:5]
                for item, count in top_items:
                    st.write(f"• **{item}:** {count} veces")
            else:
                st.info("No hay items facturados aún")
