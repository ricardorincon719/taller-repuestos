# Arquitectura SaaS de Taller Pro

## Alcance

`saas/` es la aplicación Django de producción. `app.py` y los JSON históricos solo
participan en la migración desde Streamlit y no forman parte del runtime del SaaS.

## Componentes

- `accounts`: usuario por email, activación, recuperación, aceptación legal y límites
  persistentes de autenticación.
- `organizations`: tenant, membresías y roles, invitaciones, configuración regional,
  exportación, auditoría y eliminación programada.
- `customers`: clientes y vehículos, siempre relacionados con una organización.
- `quotes`: presupuestos, ítems, numeración transaccional, snapshot de emisión, estados,
  PDF, enlaces públicos y eventos.
- `billing`: prueba, suscripción, Paddle API, checkout, portal, webhooks y notificaciones.
- `dashboard`: landing, métricas, páginas legales y comandos operativos.
- `config`: seguridad HTTP, observabilidad, salud, correo, base y configuración externa.

## Fronteras de seguridad

La organización activa se obtiene exclusivamente de una `Membership` activa del
usuario. Las consultas comerciales filtran por esa organización antes de resolver un
objeto; no se acepta un tenant enviado por el navegador como autoridad. Clientes,
vehículos y presupuestos validan además que sus relaciones pertenezcan al mismo tenant.

Los roles son:

- Propietario: pagos, exportación, eliminación y control total del equipo.
- Administrador: perfil, equipo operativo y archivo de registros; no controla pagos ni
  propiedad.
- Colaborador: trabajo diario con clientes y presupuestos, sin administración sensible.

Los enlaces de presupuesto usan UUID no predecible, vencimiento, revocación y archivo.
Al emitir un borrador se guarda un snapshot que evita que cambios posteriores del
perfil o del cliente reescriban el documento comercial ya enviado.

## Consistencia y concurrencia

- La numeración bloquea la fila de organización con `select_for_update`.
- Los cambios de estado bloquean el presupuesto y aplican una máquina de transiciones.
- Los webhooks tienen identificador único, bloqueo, firma sobre bytes crudos y control
  de orden por fecha del proveedor.
- La membresía impide eliminar o degradar al único propietario activo.
- Los totales se calculan con `Decimal`; la vista previa JavaScript no es autoridad.

PostgreSQL es obligatorio en producción. SQLite se admite únicamente para desarrollo
rápido y pruebas locales.

## Datos y archivos

El logo PNG se guarda en PostgreSQL con límite de 1 MB para no depender de un disco
efímero. Los estáticos versionados se sirven con WhiteNoise. No se almacenan números de
tarjeta: Paddle procesa los datos de pago. El exportador del propietario produce JSON
con organización, miembros, clientes, vehículos, presupuestos, eventos y suscripción.

## Runtime

El contenedor ejecuta Gunicorn como usuario sin privilegios. Render ejecuta las
migraciones en `preDeployCommand` y solo despliega automáticamente después de checks
verdes. `/health/live/` prueba el proceso y `/health/` prueba también la base.

Los logs son JSON e incluyen request ID, tiempo, ruta, estado, usuario y organización
cuando están disponibles. Sentry es opcional y se configura sin envío de PII por
defecto.

## Validación

```bash
cd saas
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test
python manage.py production_readiness
python manage.py audit_restored_database
```

En producción añade `--require-postgres --require-paddle --check-email` al comando de
preparación. La CI repite las pruebas sobre PostgreSQL, audita dependencias y ejecuta un
recorrido real con Chromium.
