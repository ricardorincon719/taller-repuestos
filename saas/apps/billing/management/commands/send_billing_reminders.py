from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.billing.models import BillingNotification, Subscription


class Command(BaseCommand):
    help = "Envía recordatorios idempotentes de prueba y pago pendiente."

    def handle(self, *args, **options):
        now = timezone.now()
        sent = 0
        trials = Subscription.objects.select_related("organization").filter(
            status=Subscription.Status.TRIALING,
            trial_ends_at__gt=now,
            trial_ends_at__lte=now + timedelta(days=3),
        )
        for subscription in trials:
            remaining = subscription.trial_ends_at - now
            days = max(0, remaining.days + (1 if remaining.seconds else 0))
            if days not in {0, 1, 3}:
                continue
            sent += self._send_once(
                subscription,
                f"trial_ending_{days}",
                subscription.trial_ends_at.date(),
                "Tu prueba de Taller Pro está por terminar",
                (
                    f"La prueba de {subscription.organization.name} termina en {days} día(s). "
                    f"Administra el plan en {settings.SITE_URL}/suscripcion/."
                ),
            )
        overdue = Subscription.objects.select_related("organization").filter(
            status=Subscription.Status.PAST_DUE, past_due_since__isnull=False
        )
        for subscription in overdue:
            sent += self._send_once(
                subscription,
                "payment_past_due",
                subscription.past_due_since.date(),
                "Tu pago de Taller Pro requiere atención",
                (
                    f"El pago de {subscription.organization.name} está pendiente. "
                    f"Actualiza el método de pago en {settings.SITE_URL}/suscripcion/."
                ),
            )
        self.stdout.write(self.style.SUCCESS(f"Recordatorios enviados: {sent}"))

    def _send_once(self, subscription, kind, reference_date, subject, body):
        if BillingNotification.objects.filter(
            subscription=subscription,
            notification_type=kind,
            reference_date=reference_date,
        ).exists():
            return 0
        recipients = list(
            subscription.organization.memberships.filter(
                role="owner", is_active=True, user__is_active=True
            ).values_list("user__email", flat=True)
        )
        if not recipients:
            return 0
        send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, recipients)
        BillingNotification.objects.create(
            subscription=subscription,
            notification_type=kind,
            reference_date=reference_date,
        )
        return 1
