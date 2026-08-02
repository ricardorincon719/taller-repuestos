# Taller Pro

SaaS Django multiempresa para talleres, oficinas y negocios de servicios en
Latinoamérica y Brasil. La aplicación de producción vive en `saas/`; la versión
Streamlit permanece únicamente como fuente de datos legados durante la transición.

## Producto incluido

- Registro con verificación por email, recuperación de contraseña y límites de abuso.
- Organizaciones aisladas, selección de negocio, propietarios, administradores,
  colaboradores e invitaciones.
- Perfil comercial regional: español o portugués de Brasil, país, moneda, zona
  horaria, datos fiscales, logo PNG y textos contractuales predeterminados.
- Clientes y vehículos con búsqueda, paginación y archivo lógico.
- Presupuestos editables mientras son borradores, ítems, descuentos, numeración
  estable, duplicación, estados comerciales, archivo y bitácora.
- Snapshot inmutable al emitir, PDF profesional, enlace temporal revocable,
  WhatsApp y aprobación o rechazo por el cliente.
- Pruebas y suscripciones Paddle, checkout, portal de cliente, webhooks firmados,
  idempotencia, tolerancia a eventos fuera de orden y recordatorios.
- Exportación completa del negocio y eliminación programada con período de gracia.
- Términos, privacidad, cookies y registro versionado de aceptación.
- PostgreSQL, Docker sin privilegios, estáticos WhiteNoise, logs JSON, request ID,
  Sentry opcional, health checks, CI, auditoría de dependencias y pruebas de navegador.

## Desarrollo y pruebas

```bash
source venv/bin/activate
pip install -r requirements-dev.txt
cd saas
python manage.py migrate
python manage.py test
python manage.py check
python manage.py makemigrations --check --dry-run
```

La prueba real de navegador es optativa en local:

```bash
RUN_BROWSER_TESTS=true python manage.py test apps.dashboard.tests.BrowserSmokeTests
```

Requiere instalar Chromium una vez con `python -m playwright install chromium`.

## Publicación

El Blueprint de Render está en `render.yaml`. Antes de abrir el servicio a clientes,
configura PostgreSQL, SMTP, Paddle, precio público, dominio y monitoreo. Después ejecuta
en el entorno de producción:

```bash
python manage.py production_readiness --require-postgres --require-paddle --check-email
```

La guía de despliegue está en [docs/DEPLOY_RENDER.md](docs/DEPLOY_RENDER.md) y el
runbook de operación, backups, restauración, incidentes y rollback en
[docs/OPERATIONS.md](docs/OPERATIONS.md).

## Documentación

- [Arquitectura SaaS](docs/SAAS_ARCHITECTURE.md)
- [Despliegue en Render](docs/DEPLOY_RENDER.md)
- [Operación de producción](docs/OPERATIONS.md)
- [Política de seguridad](SECURITY.md)

## Importación de la aplicación anterior

La importación nunca copia hashes bcrypt antiguos. Ejecuta primero una simulación y
luego la importación transaccional:

```bash
cd saas
python manage.py import_streamlit_data --dry-run
python manage.py import_streamlit_data
python manage.py import_streamlit_data --send-invitations
```

El comando es idempotente y conserva los totales, estados e identificadores históricos.
Mantén los archivos originales como respaldo hasta comparar el resultado importado.

## Licencia y soporte

Código bajo licencia MIT. El servicio alojado, soporte y operación son comerciales.
Contacto: `contacto@pearlhome.com.br`.
