from urllib.parse import urlparse

from django.conf import settings
from django.core.checks import Tags, run_checks
from django.core.mail import get_connection
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.db.migrations.executor import MigrationExecutor


class Command(BaseCommand):
    help = "Valida configuración, migraciones y servicios mínimos antes de publicar."

    def add_arguments(self, parser):
        parser.add_argument("--require-postgres", action="store_true")
        parser.add_argument("--require-paddle", action="store_true")
        parser.add_argument("--check-email", action="store_true")

    def handle(self, *args, **options):
        failures = []
        warnings = []

        checks = run_checks(
            tags=[Tags.security, Tags.database],
            include_deployment_checks=True,
            databases=["default"],
        )
        failures.extend(str(item) for item in checks if item.is_serious())
        warnings.extend(str(item) for item in checks if not item.is_serious())

        executor = MigrationExecutor(connection)
        pending = executor.migration_plan(executor.loader.graph.leaf_nodes())
        if pending:
            failures.append(
                "Hay migraciones pendientes: "
                + ", ".join(
                    f"{migration.app_label}.{migration.name}"
                    for migration, _backwards in pending
                )
            )

        if options["require_postgres"] and connection.vendor != "postgresql":
            failures.append(
                f"La base activa es {connection.vendor}; producción requiere PostgreSQL."
            )

        if settings.DEBUG:
            failures.append("DJANGO_DEBUG debe estar desactivado en producción.")
        if len(settings.SECRET_KEY) < 40 or len(set(settings.SECRET_KEY)) < 16:
            failures.append("DJANGO_SECRET_KEY debe ser largo y aleatorio.")
        for name in (
            "SESSION_COOKIE_SECURE",
            "CSRF_COOKIE_SECURE",
            "SECURE_SSL_REDIRECT",
        ):
            if not getattr(settings, name):
                failures.append(f"{name} debe estar activado.")
        if settings.SECURE_HSTS_SECONDS < 31536000:
            failures.append("SECURE_HSTS_SECONDS debe ser de al menos un año.")

        site_url = urlparse(settings.SITE_URL)
        if not settings.DEBUG and site_url.scheme != "https":
            failures.append("SITE_URL debe usar HTTPS en producción.")

        if options["require_paddle"]:
            required = {
                "PADDLE_ENABLED": settings.PADDLE_ENABLED,
                "PADDLE_CLIENT_TOKEN": settings.PADDLE_CLIENT_TOKEN,
                "PADDLE_API_KEY": settings.PADDLE_API_KEY,
                "PADDLE_WEBHOOK_SECRET": settings.PADDLE_WEBHOOK_SECRET,
                "PADDLE_PRICE_ID": settings.PADDLE_PROFESSIONAL_PRICE_ID
                or settings.PADDLE_STARTER_PRICE_ID,
            }
            missing = [name for name, value in required.items() if not value]
            if missing:
                failures.append("Configuración Paddle incompleta: " + ", ".join(missing))

        if options["check_email"]:
            try:
                email_connection = get_connection(fail_silently=False)
                opened = email_connection.open()
                email_connection.close()
                if opened is False:
                    failures.append("El backend SMTP no pudo abrir una conexión.")
            except Exception as exc:
                failures.append(f"Falló la conexión de correo: {exc}")

        for warning in warnings:
            self.stdout.write(self.style.WARNING(warning))
        if failures:
            raise CommandError("\n".join(failures))
        self.stdout.write(
            self.style.SUCCESS(
                f"Producción lista: DB={connection.vendor}, migraciones=ok, "
                f"Paddle={'validado' if options['require_paddle'] else 'omitido'}, "
                f"correo={'validado' if options['check_email'] else 'omitido'}."
            )
        )
