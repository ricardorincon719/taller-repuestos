# Runbook de producción de Taller Pro

## Responsables y servicios

Registra fuera del repositorio el responsable primario y suplente de aplicación,
facturación, correo y privacidad. Mantén accesos de emergencia protegidos con MFA y un
gestor de contraseñas. Inventario mínimo: GitHub, Render web, Render PostgreSQL, Paddle,
SMTP, DNS y Sentry.

## Checklist de cada release

1. CI verde: PostgreSQL, migraciones, suite Django, auditoría de dependencias y Chromium.
2. Revisa que cada migración sea compatible con la versión anterior; usa cambios
   expand/contract para columnas destructivas o grandes.
3. Confirma que no hay secretos, `.env`, dumps ni datos de clientes en el diff.
4. Verifica el entorno de Paddle y el texto público de precio.
5. Publica primero en un entorno de prueba con una copia anonimizada o datos sintéticos.
6. Crea/valida un punto de recuperación antes de una migración sensible.
7. Despliega. Render ejecuta `python manage.py migrate --noinput` antes de reemplazar el
   servicio.
8. Ejecuta:

```bash
python manage.py production_readiness --require-postgres --require-paddle --check-email
python manage.py audit_restored_database
```

9. Prueba login, dashboard, alta de cliente, presupuesto, PDF, enlace público y salud.
10. Observa errores, latencia, reinicios y webhooks durante al menos 15 minutos.

## Monitoreo y alertas

- Monitor externo cada minuto sobre `/health/`; alerta después de dos fallos.
- Monitor separado sobre `/health/live/` para distinguir proceso de base de datos.
- Sentry: alertas inmediatas para errores nuevos y picos; no habilitar PII por defecto.
- Render: CPU, memoria, reinicios, uso y conexiones de PostgreSQL, disco y tareas cron.
- Paddle: webhooks fallidos, pagos pendientes y cancelaciones inesperadas.
- SMTP: rechazos, rebotes y reputación del dominio.
- Capacidad: revisar semanalmente tiempos p95, tamaño de DB y crecimiento de presupuestos.

Los logs JSON se correlacionan por el encabezado `X-Request-ID`. No pegues payloads de
clientes, cookies, tokens o secretos en tickets.

## Backups

1. Render activa PITR en bases pagadas. La ventana actual es de 3 días en workspace
   Hobby y 7 días en Pro o superior; confírmala en `Recovery` porque depende del plan.
   Los exports lógicos creados desde Render se conservan 7 días, por lo que deben
   descargarse si se necesita retención más larga.
2. Antes de releases de datos, genera un backup lógico cifrado desde una máquina segura:

```bash
pg_dump --format=custom --no-owner --no-acl "$DATABASE_URL" > taller-pro-UTC.dump
```

3. Cifra el archivo y súbelo a almacenamiento privado con versionado, MFA y ciclo de vida.
4. No guardes dumps en Git, el contenedor, `/tmp` persistente ni equipos compartidos.
5. Registra fecha, entorno, tamaño, hash SHA-256, responsable y resultado.
6. Retén según obligaciones comerciales y legales; documenta la política definitiva.

Referencias operativas: [recovery y backups de Render](https://render.com/docs/postgresql-backups)
y [backup adicional a S3](https://render.com/docs/backup-postgresql-to-s3).

## Simulacro de restauración

Ejecuta al menos trimestralmente y antes de cambios de alto riesgo:

1. Crea PostgreSQL vacío, aislado y sin salida de email/Paddle.
2. Restaura:

```bash
createdb taller_pro_restore_test
pg_restore --no-owner --no-acl --exit-on-error --dbname="$RESTORE_DATABASE_URL" taller-pro-UTC.dump
```

3. Apunta un servicio temporal a la base restaurada con `PADDLE_ENABLED=false` y backend
   de correo local.
4. Ejecuta:

```bash
python manage.py migrate --noinput
python manage.py audit_restored_database
python manage.py check --deploy
```

5. Compara los conteos contra el registro del backup y abre presupuestos/PDF de varias
   organizaciones sin cruzar datos.
6. Mide RPO y RTO, registra resultado y destruye de forma segura la copia temporal.

## Incidentes

1. Declara severidad, hora y responsable. Conserva logs y request IDs.
2. Contén: pausa deploys; revoca tokens o desactiva checkout solo si el incidente lo exige.
3. Si existe riesgo de acceso entre tenants, suspende temporalmente el servicio y preserva
   evidencia antes de modificar datos.
4. Rota credenciales comprometidas en proveedor y Render; nunca reutilices el secreto.
5. Recupera desde la última versión o backup verificado.
6. Valida salud, integridad, aislamiento, correo y facturación antes de reabrir.
7. Comunica a clientes y autoridades dentro de los plazos aplicables cuando corresponda.
8. Redacta postmortem con causa, impacto, línea temporal, correcciones y prevención.

## Rollback

- Código sin migración incompatible: redeploy del commit anterior y smoke test.
- Migración expand/contract: vuelve el código y conserva las columnas nuevas hasta una
  limpieza posterior.
- Migración destructiva o corrupción: detén escrituras, restaura a una base nueva, ejecuta
  `audit_restored_database`, cambia `DATABASE_URL` y reabre solo después de validar.
- No reviertas migraciones con pérdida de datos improvisando comandos sobre producción.

## Tareas programadas

El cron diario ejecuta, en orden:

```bash
python manage.py send_billing_reminders
python manage.py cleanup_security_data
python manage.py purge_scheduled_organizations
```

Revisa su resultado diariamente. La última tarea elimina definitivamente organizaciones
cuyo período de gracia terminó; la recuperación posterior depende exclusivamente de los
backups y de la retención legal definida.
