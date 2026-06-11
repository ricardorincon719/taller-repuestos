# Despliegue de Taller Pro en Render

Esta guía publica el SaaS Django con PostgreSQL administrado, HTTPS y correo SMTP.
El archivo `render.yaml` crea la aplicación y la base de datos en la misma región.

## Coste mínimo recomendado

A fecha del 11 de junio de 2026, la configuración usa:

- Render Web Service Starter: USD 7/mes.
- Render Postgres Basic-256mb: USD 6/mes.
- Brevo: puede iniciarse con su plan disponible para correo transaccional.

No uses el servicio web gratuito para esta prueba: Render bloquea las salidas SMTP por
los puertos 25, 465 y 587. Su PostgreSQL gratuito también caduca a los 30 días.

Referencias:

- https://render.com/pricing
- https://render.com/docs/free
- https://render.com/docs/deploy-django

## 1. Publicar el código en GitHub

El repositorio debe contener y tener confirmados en GitHub `render.yaml`,
`Dockerfile.saas`, `requirements-saas.txt` y el directorio `saas/`.

No subas archivos `.env`, contraseñas SMTP ni URLs privadas de PostgreSQL.

## 2. Crear la cuenta SMTP en Brevo

1. Crea una cuenta en https://www.brevo.com/.
2. En remitentes y dominios, verifica el email que enviará las activaciones.
3. En SMTP y API, crea una nueva clave SMTP.
4. Guarda el login SMTP y la clave SMTP. La clave no es la contraseña normal de Brevo.

Para una beta puede verificarse un remitente individual. Antes de vender el servicio,
conviene usar un dominio propio y configurar SPF, DKIM y DMARC.

## 3. Crear Render Blueprint

1. Crea una cuenta en https://dashboard.render.com/ usando GitHub.
2. Abre `New > Blueprint`.
3. Conecta el repositorio de Taller Pro.
4. Render detectará `render.yaml` y propondrá:
   - `taller-pro-saas`, servicio web Starter.
   - `taller-pro-db`, PostgreSQL Basic-256mb.
5. Completa las variables marcadas como secretas:

```text
DEFAULT_FROM_EMAIL=Taller Pro <email-verificado@tu-dominio.com>
EMAIL_HOST_USER=login-smtp-entregado-por-brevo
EMAIL_HOST_PASSWORD=clave-smtp-entregada-por-brevo
```

6. Aplica el Blueprint. Render generará `DJANGO_SECRET_KEY`, conectará
   `DATABASE_URL`, ejecutará migraciones y publicará una URL HTTPS.

`RENDER_EXTERNAL_HOSTNAME` configura automáticamente `ALLOWED_HOSTS`,
`CSRF_TRUSTED_ORIGINS` y `SITE_URL` para la URL inicial de Render.

## 4. Crear el administrador Django

Cuando el despliegue esté activo, abre `Shell` en el servicio web y ejecuta:

```bash
python manage.py createsuperuser
```

La cuenta administrativa sirve para `/admin/`. Las cuentas normales de los talleres se
crean desde `/cuenta/registro/` y deben activarse mediante el correo recibido.

## 5. Prueba real desde otros dispositivos

1. Abre `https://URL-DE-RENDER/health/`; debe responder `{"status": "ok"}`.
2. Desde el celular con datos móviles, abre `/cuenta/registro/`.
3. Registra un taller con un email real.
4. Comprueba recepción, enlace de activación, inicio de sesión y recuperación de clave.
5. Crea un cliente y un presupuesto, descarga el PDF y prueba el enlace público.

Revisa también spam, tiempo de entrega y los logs de Render y Brevo.

## 6. Dominio propio

Al conectar, por ejemplo, `app.tallerpro.com`, agrega en Render:

```text
DJANGO_ALLOWED_HOSTS=app.tallerpro.com
DJANGO_CSRF_TRUSTED_ORIGINS=https://app.tallerpro.com
SITE_URL=https://app.tallerpro.com
```

Después configura el registro DNS indicado por Render. No actives HSTS preload hasta
comprobar que todos los subdominios funcionan permanentemente por HTTPS.

## 7. Antes de clientes reales

- Configura alertas y revisa la política de backups de PostgreSQL.
- Activa autenticación de dos factores en GitHub, Render y Brevo.
- Mantén separados los secretos de prueba y producción.
- Completa pagos y webhooks antes de cobrar suscripciones.
