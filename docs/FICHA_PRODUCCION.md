# Ficha de datos para producción de Taller Pro

Fecha de revisión: ____ / ____ / ______

Responsable de completar la ficha: ______________________________

## Instrucciones de seguridad

Esta ficha puede contener datos comerciales y legales, pero **no debe contener
contraseñas ni secretos**.

No escribas aquí:

- API keys de Paddle.
- Client tokens completos.
- Webhook secrets.
- Contraseñas SMTP.
- `DJANGO_SECRET_KEY`.
- URL privada de PostgreSQL.
- Contraseñas de usuarios o del administrador.

Para esos valores, marca solamente si ya fueron configurados directamente en Render.

## 1. Identidad comercial y legal

- Nombre público del producto: Taller Pro
- Forma de operación: persona física
- Nombre legal completo del responsable: Ricardo Rincón
- Nombre comercial, si es diferente: Taller-Repuestos
- Tipo de identificación fiscal: CPF
- Número de CPF: conservado de forma privada; no escribir en este repositorio
- Dirección legal completa: Rua Boaventura de souza 50, sobrado
- Ciudad: Caraguatatuba
- Estado, provincia o departamento: SP
- Código postal: 11670-140
- País: Brasil
- Jurisdicción aplicable para los términos: Brasil, Estado de São Paulo
- Correo de privacidad y asuntos legales: soporte.tallerpro@gmail.com **(Confirmado)**
- Correo de soporte al cliente: soporte.tallerpro@gmail.com
- Teléfono o WhatsApp de soporte, si se publicará: +5512981123332

Confirmaciones:

- [X] Autorizo publicar el nombre legal en los términos y la política de privacidad.
- [X] Autorizo publicar la dirección legal.
- [X] Autorizo publicar el correo legal.
- [X] Los términos y la política de privacidad fueron revisados para el negocio real.

## 2. Dominio y Render

- Servicio Render: `taller-pro-saas`
- URL pública: `https://taller-pro-saas-xqoq.onrender.com`
- Host permitido: `taller-pro-saas-xqoq.onrender.com`
- Origen CSRF: `https://taller-pro-saas-xqoq.onrender.com`
- Base de datos esperada: PostgreSQL administrado por Render

Confirmaciones:

- [x] La URL pública responde por HTTPS.
- [X] El plan del servicio web es apto para producción.
- [x] PostgreSQL es persistente y no expira.
- [x] La tarea diaria `taller-pro-maintenance` está creada.
- [x] Acepto el costo mensual de servicio web, PostgreSQL y cron.
- [x] MFA está activado en Render y GitHub.

## 3. Plan comercial

- Nombre del plan: Taller Pro Profesional
- Precio numérico mensual: 20,00
- Moneda, por ejemplo USD, BRL o COP: USD
- Texto público exacto, por ejemplo `US$ 19 por mes`: US$ 19,99 por mes
- Días de prueba: 14
- Fecha prevista de lanzamiento: 03/08/2026

Confirmaciones:

- [x] El precio público coincide con el precio configurado en Paddle.
- [x] La moneda y periodicidad se muestran claramente antes del checkout.
- [x] Está definida la política comercial de cancelación y reembolso.

## 4. Paddle

- Cuenta/producto: Taller-repuestos
- Seller ID: `393039`
- Price ID de producción: `pri_01kz1srt3bwj63crcbs85a1531`
- Webhook: `https://taller-pro-saas-xqoq.onrender.com/suscripcion/webhook/paddle/`

Eventos requeridos:

- [x] `subscription.created`
- [x] `subscription.updated`
- [x] `subscription.canceled`

Secretos, marcar sin escribir valores:

- [x] La API key expuesta anteriormente fue revocada.
- [x] Se creó una API key nueva.
- [x] Se rotó el client-side token.
- [ ] La nueva API key está guardada como `PADDLE_API_KEY` en Render.
- [ ] El nuevo client token está guardado como `PADDLE_CLIENT_TOKEN` en Render.
- [ ] El endpoint secret está guardado como `PADDLE_WEBHOOK_SECRET` en Render.
- [ ] `PADDLE_ENVIRONMENT=production`.
- [ ] `PADDLE_ENABLED=true`.
- [ ] Se verificó un checkout real controlado.
- [ ] El webhook aparece procesado sin errores.
- [ ] Se verificó el portal de facturación y cancelación.

## 5. Correo transaccional

- Proveedor SMTP, recomendado Brevo: ______________________________
- Correo remitente visible: ______________________________
- Nombre visible del remitente: Taller Pro
- Host SMTP: `smtp-relay.brevo.com` o ______________________________
- Puerto SMTP: `587` o ______________________________
- Correo que recibirá errores operativos: ______________________________

Secretos, marcar sin escribir valores:

- [ ] El remitente está verificado en el proveedor SMTP.
- [ ] SPF está configurado, si se usa un dominio propio.
- [ ] DKIM está configurado, si se usa un dominio propio.
- [ ] DMARC está configurado, si se usa un dominio propio.
- [ ] `DEFAULT_FROM_EMAIL` está configurado en Render.
- [ ] `EMAIL_HOST_USER` está configurado en Render.
- [ ] `EMAIL_HOST_PASSWORD` está configurado en Render.
- [ ] Se recibió correctamente un correo de activación.
- [ ] Se recibió correctamente un correo de recuperación de contraseña.
- [ ] Se revisó la carpeta de spam.

## 6. Administración y soporte

- Nombre del administrador inicial: Ricardo Rincón
- Correo del administrador inicial: ricardorincon719@gmail.com
- Horario de soporte anunciado: ______________________________
- Tiempo objetivo de respuesta: 1 dia
- Persona responsable de incidentes: Ricardo Rincon
- Medio alternativo de contacto: ______________________________

Confirmaciones:

- [ ] Se creó un superusuario separado para `/admin/`.
- [ ] El superusuario usa una contraseña única y segura.
- [ ] El superusuario no se utilizará como cuenta diaria del producto.
- [ ] MFA está activado en Paddle y en el proveedor SMTP.

## 7. Observabilidad, respaldo y recuperación

- Proveedor de errores: Sentry / otro / pendiente: ______________________________
- Canal para alertas: ______________________________
- Responsable de revisar alertas: ______________________________

Confirmaciones:

- [ ] `SENTRY_DSN` está configurado en Render, si se utilizará Sentry.
- [ ] Se recibió un evento controlado de prueba en Sentry.
- [ ] Está confirmada la política de backups del plan PostgreSQL.
- [ ] Se verificó una restauración o una copia restaurada.
- [ ] Se revisó el procedimiento de rollback.
- [ ] Existe una persona responsable de responder incidentes.

## 8. Prueba final del producto

- [ ] `/health/live/` responde con estado `alive`.
- [ ] `/health/` responde con estado `ok`.
- [ ] Registro de un taller nuevo.
- [ ] Activación por correo.
- [ ] Inicio de sesión y recuperación de contraseña.
- [ ] Perfil del taller, logo y configuración regional.
- [ ] Invitación de colaborador y verificación de permisos.
- [ ] Creación de cliente y vehículo.
- [ ] Presupuesto con varios ítems y cálculos correctos.
- [ ] Emisión y descarga del PDF.
- [ ] Enlace público, aprobación, rechazo y revocación.
- [ ] Checkout Paddle real controlado.
- [ ] Webhook de suscripción procesado.
- [ ] Portal de pagos y cancelación.
- [ ] Exportación JSON del negocio.
- [ ] Solicitud y cancelación de eliminación de cuenta.
- [ ] Revisión desde teléfono móvil y otra conexión de internet.

## 9. Autorización de publicación

- [ ] Toda la información anterior fue completada y revisada.
- [ ] Las credenciales están solamente en Render o en el proveedor correspondiente.
- [ ] Autorizo hacer commit de los cambios del producto.
- [ ] Autorizo hacer push a la rama `main`.
- [ ] Autorizo desplegar la versión final en Render.
- [ ] Autorizo invitar al primer cliente después de completar el smoke test.

Nombre: ______________________________

Fecha: ______________________________

Decisión final (`AUTORIZADO` o `NO AUTORIZADO`): ______________________________
