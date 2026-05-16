# 🔧 Taller Presupuestos

Sistema profesional para gestión de presupuestos en talleres mecánicos.

## 🚀 Versión en línea

**URL:** [taller-presupuestos.streamlit.app](https://taller-repuestos.streamlit.app/)

## ✨ Características

- ✅ Creación rápida de presupuestos
- ✅ Historial de clientes
- ✅ Estadísticas automáticas
- ✅ Interfaz responsive (funciona en celular)
- ✅ Sin instalación, solo navegador

## 💼 ¿Quieres usar este sistema en tu taller?

Ofrezco el sistema como servicio (SaaS) con:
- Soporte por WhatsApp
- Personalización con tu logo
- Backup automático de datos

**Contacto:** ricardorincon5512@gmail.com tel: +5512981123332

## 📄 Licencia

MIT License - Puedes usar y modificar el código, pero la versión alojada en [URL] es un servicio comercial.

---

## ⚙️ Despliegue y configuración (importante para producción SaaS)

Este proyecto requiere algunas variables de entorno para que las credenciales y secretos no estén en el código fuente. Crea un archivo `.env` (no lo subas al repositorio) o define las variables en tu plataforma de despliegue (p. ej. Streamlit Cloud, Heroku, Docker):

- `ADMIN_PASSWORD` - Contraseña administrativa para el panel de administración.
- `MASTER_ACTIVATION_KEY` - Clave maestra para activar licencias (guárdala segura).
- `COOKIE_PASSWORD` - Contraseña para cifrar cookies (utilizada por streamlit-cookies-manager).

Hemos incluido `.env.example` con placeholders.

Recomendaciones para producción:
- Rotar secretos regularmente y no usar los valores de ejemplo.
- Usar un servicio persistente (SQLite, PostgreSQL o un storage en la nube) cuando la aplicación crezca; los JSON en `data/` son adecuados para prototipos.
- Configurar backups automáticos y no exponer `data/` ni `backups/` públicamente.
- Establecer HTTPS y políticas de seguridad en la plataforma de hosting.

