from datetime import timedelta

from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Count
from django.utils import timezone

from apps.accounts.models import RateLimitBucket, User
from apps.organizations.models import Organization


class Command(BaseCommand):
    help = "Limpia sesiones, límites vencidos y registros inactivos abandonados."

    def handle(self, *args, **options):
        call_command("clearsessions")
        rate_limits, _ = RateLimitBucket.objects.filter(
            updated_at__lt=timezone.now() - timedelta(days=2)
        ).delete()
        cutoff = timezone.now() - timedelta(days=30)
        with transaction.atomic():
            abandoned_organizations = Organization.objects.annotate(
                member_count=Count("memberships")
            ).filter(
                member_count=1,
                memberships__user__is_active=False,
                memberships__user__date_joined__lt=cutoff,
                memberships__user__legal_acceptances__isnull=False,
            )
            abandoned_count = abandoned_organizations.count()
            abandoned_organizations.delete()
            inactive, _ = User.objects.filter(
                is_active=False,
                date_joined__lt=cutoff,
                legal_acceptances__isnull=False,
                organization_memberships__isnull=True,
            ).delete()
        self.stdout.write(
            self.style.SUCCESS(
                f"Límites eliminados: {rate_limits}; negocios abandonados: "
                f"{abandoned_count}; usuarios inactivos: {inactive}"
            )
        )
