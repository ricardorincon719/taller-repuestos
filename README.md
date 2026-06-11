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

## Nueva arquitectura SaaS

El MVP Django vive en `saas/` y funciona en paralelo con la aplicación Streamlit.
Incluye registro y activación por email, aislamiento multiempresa, clientes, vehículos,
presupuestos, PDF, enlaces para WhatsApp, importación de datos y control de acceso por
suscripción. PostgreSQL administrado, pagos y despliegue beta requieren infraestructura
externa. Consulta [`docs/SAAS_ARCHITECTURE.md`](docs/SAAS_ARCHITECTURE.md) para
configurar, ejecutar y probar la nueva base.
