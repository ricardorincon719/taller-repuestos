# Despliegue de Taller Pro en Render

El Blueprint `render.yaml` crea el servicio web, PostgreSQL y la tarea diaria de
mantenimiento. El despliegue usa HTTPS, migraciones previas, Gunicorn sin privilegios y
solo se activa después de que la CI de GitHub termine correctamente.

## 1. Preparar cuentas y dominio

1. Activa MFA en GitHub, Render, Paddle, el proveedor SMTP y Sentry.
2. Verifica un dominio y un remitente SMTP; publica SPF, DKIM y DMARC.
3. Crea en Paddle el producto y precio recurrente definitivo.
4. Decide la entidad legal, email de privacidad, jurisdicción y texto público del precio.
5. Revisa los términos y la política de privacidad con asesoría aplicable al negocio real.

No uses planes efímeros o una base que expire para clientes reales. Confirma en Render
la retención y recuperación disponibles en el plan PostgreSQL elegido.

## 2. Publicar el Blueprint

1. Confirma en GitHub `render.yaml`, `Dockerfile.saas`, requisitos, migraciones y `saas/`.
2. En Render abre `New > Blueprint` y conecta el repositorio.
3. Antes de aplicar, completa todas las variables `sync: false`:

```text
DEFAULT_FROM_EMAIL=Taller Pro <no-reply@tu-dominio.com>
EMAIL_HOST_USER=<usuario SMTP>
EMAIL_HOST_PASSWORD=<clave SMTP>
PADDLE_CLIENT_TOKEN=<token público de Paddle.js>
PADDLE_API_KEY=<API key privada>
PADDLE_WEBHOOK_SECRET=<secret del notification destination>
SENTRY_DSN=<DSN de producción>
```

Render genera `DJANGO_SECRET_KEY`, conecta `DATABASE_URL` y expone
`RENDER_EXTERNAL_HOSTNAME`. La aplicación deriva de este último los hosts, orígenes CSRF
y URL inicial. El Blueprint fija actualmente la URL pública
`https://taller-pro-saas-xqoq.onrender.com` tanto para el servicio web como para la
tarea de mantenimiento. La identidad legal autorizada, el contacto, la jurisdicción y
el precio público también están definidos como valores públicos del Blueprint. Incluye
el precio mensual de Paddle
`pri_01kz1srt3bwj63crcbs85a1531`; este identificador no es una credencial secreta.
Nunca copies secretos de sandbox a producción.

## 3. Configurar Paddle

1. Usa `PADDLE_ENVIRONMENT=production`; conserva sandbox en un servicio separado.
2. En Paddle crea un notification destination con la URL:

   `https://taller-pro-saas-xqoq.onrender.com/suscripcion/webhook/paddle/`

3. Suscribe como mínimo `subscription.created`, `subscription.updated` y
   `subscription.canceled`.
4. Copia el endpoint secret a `PADDLE_WEBHOOK_SECRET`.
5. Verifica un checkout real controlado, el portal, una cancelación y un evento
   `past_due`. Confirma que cada evento aparece procesado en `/admin/` sin error.

El token cliente solo se entrega a Paddle.js. La API key y el webhook secret permanecen
en el servidor.

## 4. Dominio

Al conectar `app.tu-dominio.com`, define explícitamente:

```text
DJANGO_ALLOWED_HOSTS=app.tu-dominio.com
DJANGO_CSRF_TRUSTED_ORIGINS=https://app.tu-dominio.com
SITE_URL=https://app.tu-dominio.com
```

Mantén `DJANGO_SECURE_HSTS_PRELOAD=false` hasta verificar que todos los subdominios
funcionan permanentemente por HTTPS.

## 5. Validación obligatoria

Desde el Shell del servicio web:

```bash
python manage.py production_readiness --require-postgres --require-paddle --check-email
python manage.py audit_restored_database
```

Luego valida:

1. `/health/live/` responde `{"status":"alive"}`.
2. `/health/` responde `{"status":"ok"}`.
3. Registro, recepción del email, activación, login y recuperación de contraseña.
4. Perfil regional, logo, invitación y permisos de colaborador/administrador.
5. Cliente, vehículo, borrador con varios ítems, emisión, PDF y WhatsApp.
6. Aprobación pública, revocación del enlace, duplicación y facturación.
7. Checkout Paddle, portal, webhook y acceso después del pago.
8. Exportación JSON del negocio y solicitud/cancelación de eliminación.
9. Sentry recibe un evento de prueba controlado y los logs incluyen `X-Request-ID`.

No invites al primer cliente hasta que toda esta lista pase en el dominio definitivo.

## 6. Administración

Si se necesita acceso operativo a `/admin/`, crea una cuenta independiente:

```bash
python manage.py createsuperuser
```

No uses esa cuenta como usuario diario del producto. El runbook completo de releases,
backups, restore, monitoreo y rollback está en `OPERATIONS.md`.
