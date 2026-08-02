from django.core.management.base import BaseCommand, CommandError
from django.db.models import Count, F

from apps.accounts.models import User
from apps.customers.models import Customer, Vehicle
from apps.organizations.models import Membership, Organization
from apps.quotes.models import Quote, QuoteItem


class Command(BaseCommand):
    help = "Audita una base restaurada sin modificarla y muestra conteos reproducibles."

    def handle(self, *args, **options):
        problems = []
        organizations_without_owner = Organization.objects.filter(is_active=True).exclude(
            memberships__role=Membership.Role.OWNER,
            memberships__is_active=True,
        ).count()
        if organizations_without_owner:
            problems.append(
                f"Organizaciones activas sin propietario: {organizations_without_owner}"
            )
        bad_vehicles = Vehicle.objects.exclude(
            organization=F("customer__organization")
        ).count()
        bad_quotes = Quote.objects.exclude(
            organization=F("customer__organization")
        ).count()
        bad_quote_vehicles = Quote.objects.filter(vehicle__isnull=False).exclude(
            organization=F("vehicle__organization"),
            customer=F("vehicle__customer"),
        ).count()
        invalid_next_numbers = Quote.objects.filter(
            number__gte=F("organization__next_quote_number")
        ).count()
        duplicate_numbers = (
            Quote.objects.values("organization_id", "number")
            .annotate(total=Count("id"))
            .filter(total__gt=1)
            .count()
        )
        if bad_vehicles:
            problems.append(f"Vehículos fuera de su organización: {bad_vehicles}")
        if bad_quotes:
            problems.append(f"Presupuestos fuera de su organización: {bad_quotes}")
        if bad_quote_vehicles:
            problems.append(
                f"Presupuestos con vehículo inconsistente: {bad_quote_vehicles}"
            )
        if invalid_next_numbers:
            problems.append(
                f"Presupuestos fuera de la secuencia siguiente: {invalid_next_numbers}"
            )
        if duplicate_numbers:
            problems.append(f"Números de presupuesto duplicados: {duplicate_numbers}")

        self.stdout.write(
            " ".join(
                [
                    f"organizations={Organization.objects.count()}",
                    f"users={User.objects.count()}",
                    f"memberships={Membership.objects.count()}",
                    f"customers={Customer.objects.count()}",
                    f"vehicles={Vehicle.objects.count()}",
                    f"quotes={Quote.objects.count()}",
                    f"quote_items={QuoteItem.objects.count()}",
                ]
            )
        )
        if problems:
            raise CommandError("; ".join(problems))
        self.stdout.write(self.style.SUCCESS("Integridad básica de la restauración: OK"))
