# Arquitectura SaaS

La nueva aplicación Django vive en `saas/` y se desarrolla en paralelo a la versión
Streamlit. Durante la transición, `app.py` continúa siendo el punto de entrada del
despliegue actual.

## Módulos

- `organizations`: talleres, miembros y roles.
- `customers`: clientes y vehículos.
- `quotes`: presupuestos, ítems, numeración y totales.
- `billing`: estado de suscripción y registro idempotente de webhooks.
- `dashboard`: panel autenticado del taller.

Toda entidad comercial contiene una relación con `Organization`. Las vistas obtienen
el taller desde una membresía activa y filtran las consultas antes de acceder a los
datos. La numeración de presupuestos usa una transacción y bloqueo de fila, diseñado
para PostgreSQL.

## Desarrollo local

```bash
source venv/bin/activate
pip install -r requirements-saas.txt
cd saas
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Abre `/cuenta/registro/` para crear un taller. El propietario recibirá un correo de
activación y, después de verificarlo, podrá administrar clientes, vehículos y
presupuestos sin pasar por `/admin/`.

## Pruebas

Ejecuta las pruebas desde la raíz Django para que el descubrimiento incluya todos los
módulos:

```bash
cd saas
../venv/bin/python manage.py test
```

## Producción

La producción requiere PostgreSQL, una URL pública HTTPS y un backend de correo real
con las variables descritas en `.env.saas.example`. El proceso se niega a arrancar si
faltan la clave secreta, hosts, base de datos, URL pública o configuración de correo.
También deben configurarse backups externos, monitoreo y el proveedor de pagos.

La guía operativa para crear PostgreSQL, SMTP y publicar la beta está en
[`DEPLOY_RENDER.md`](DEPLOY_RENDER.md).

El contenedor se construye con:

```bash
docker build -f Dockerfile.saas -t taller-pro-saas .
```

## Estado de la transición

Completado en el MVP Django:

- PDF descargable por presupuesto.
- Enlace público no predecible para el cliente y envío mediante WhatsApp.
- Cambio de estado del presupuesto desde la interfaz.
- Control de acceso para pruebas vigentes y suscripciones activas.
- Pantalla de suscripción para pruebas vencidas, pagos pendientes y cancelaciones.
- Límite configurable de registros por IP y email, compartido entre workers del contenedor.
- Migraciones automáticas antes de iniciar Gunicorn.

Pendiente de servicios e infraestructura externos:

1. Elegir el proveedor de pagos e integrar checkout y webhooks firmados reales.
2. Configurar un servicio de entregabilidad de correo y protección antiabuso distribuida.
3. Ejecutar las pruebas de aislamiento y concurrencia contra PostgreSQL administrado.
4. Configurar backups, monitoreo, dominio HTTPS y desplegar la beta separada.
5. Migrar talleres piloto después de validar la importación y los correos.

## Importación desde Streamlit

El comando valida ambos JSON y ejecuta toda la migración dentro de una sola
transacción. Nunca copia los hashes bcrypt antiguos: los usuarios quedan con una
contraseña inutilizable y deben definir una nueva mediante el flujo de recuperación.

Primero ejecuta una simulación:

```bash
cd saas
../venv/bin/python manage.py import_streamlit_data --dry-run
```

Después importa los datos:

```bash
../venv/bin/python manage.py import_streamlit_data
```

Cuando el backend de correo de producción esté verificado, envía las invitaciones:

```bash
../venv/bin/python manage.py import_streamlit_data --send-invitations
```

El comando es idempotente: identifica cada presupuesto por su taller, origen e ID
histórico. Puede repetirse sin duplicar usuarios, clientes o presupuestos. Los archivos
originales deben conservarse como respaldo hasta validar los datos en PostgreSQL.
