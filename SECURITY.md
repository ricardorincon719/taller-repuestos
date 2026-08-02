# Seguridad de Taller Pro

## Reporte de vulnerabilidades

No publiques vulnerabilidades ni datos reales en un issue. Envía el reporte a
`contacto@pearlhome.com.br` con la ruta afectada, impacto, pasos mínimos para reproducir
y, si existe, una propuesta de mitigación. No incluyas credenciales, tarjetas ni datos
de clientes en el mensaje.

## Controles principales

- Aislamiento multiempresa mediante membresías del servidor y filtros por organización.
- Roles separados para operación, administración, propiedad y facturación.
- Contraseñas de Django, activación por email, recuperación expirable y rate limiting.
- CSRF, cookies seguras y HTTP-only, HTTPS, HSTS, CSP, anti-clickjacking y políticas de
  contenido/referrer.
- Webhooks Paddle firmados sobre el cuerpo crudo, idempotentes y resistentes a eventos
  atrasados.
- Secretos únicamente en variables protegidas; nunca en Git, imágenes ni logs.
- Logs con identificadores técnicos y sin contenido de presupuestos ni contraseñas.
- Dependabot, `pip-audit`, checks de despliegue, pruebas de PostgreSQL y navegador.
- Exportación y eliminación programada con período de gracia.

## Operación segura

Activa MFA en GitHub, Render, Paddle, SMTP y monitoreo. Limita los administradores,
rota cualquier secreto expuesto, revisa semanalmente alertas y accesos, y ejecuta un
simulacro trimestral de restauración. Antes de usar HSTS preload verifica todos los
subdominios. Los documentos legales incluidos deben ser revisados por asesoría aplicable
a la entidad, país, precio y política comercial reales antes de cobrar.

Las instrucciones de respuesta a incidentes y recuperación están en
`docs/OPERATIONS.md`.
