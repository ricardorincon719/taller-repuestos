from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.organizations.models import OrganizationDeletionRequest


class Command(BaseCommand):
    help = "Elimina definitivamente organizaciones cuyo período de gracia terminó."

    def handle(self, *args, **options):
        requests = OrganizationDeletionRequest.objects.filter(
            cancelled_at__isnull=True, execute_after__lte=timezone.now()
        ).select_related("organization")
        deleted = 0
        for deletion_request in requests:
            with transaction.atomic():
                organization = deletion_request.organization
                users = list(organization.memberships.values_list("user_id", flat=True))
                organization.delete()
                from apps.accounts.models import User

                User.objects.filter(pk__in=users, organization_memberships__isnull=True).delete()
                deleted += 1
        self.stdout.write(self.style.SUCCESS(f"Organizaciones eliminadas: {deleted}"))
