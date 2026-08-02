from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.organizations.models import Organization


class Subscription(models.Model):
    class Plan(models.TextChoices):
        TRIAL = "trial", _("Prueba")
        STARTER = "starter", _("Inicial")
        PROFESSIONAL = "professional", _("Profesional")

    class Status(models.TextChoices):
        TRIALING = "trialing", _("En prueba")
        ACTIVE = "active", _("Activa")
        PAST_DUE = "past_due", _("Pago pendiente")
        PAUSED = "paused", _("Pausada")
        CANCELLED = "cancelled", _("Cancelada")

    organization = models.OneToOneField(
        Organization,
        on_delete=models.CASCADE,
        related_name="subscription",
    )
    plan = models.CharField(max_length=24, choices=Plan.choices, default=Plan.TRIAL)
    status = models.CharField(
        max_length=24,
        choices=Status.choices,
        default=Status.TRIALING,
    )
    provider_customer_id = models.CharField(max_length=120, blank=True)
    provider_subscription_id = models.CharField(max_length=120, blank=True)
    provider_price_id = models.CharField(max_length=120, blank=True)
    trial_ends_at = models.DateTimeField(null=True, blank=True)
    current_period_ends_at = models.DateTimeField(null=True, blank=True)
    past_due_since = models.DateTimeField(null=True, blank=True)
    provider_last_event_at = models.DateTimeField(null=True, blank=True)
    cancel_at_period_end = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "suscripción"
        verbose_name_plural = "suscripciones"
        constraints = [
            models.UniqueConstraint(
                fields=("provider_customer_id",),
                condition=~models.Q(provider_customer_id=""),
                name="unique_nonempty_provider_customer",
            ),
            models.UniqueConstraint(
                fields=("provider_subscription_id",),
                condition=~models.Q(provider_subscription_id=""),
                name="unique_nonempty_provider_subscription",
            ),
        ]

    @property
    def allows_access(self):
        if self.status == self.Status.ACTIVE:
            return True
        if self.status == self.Status.PAST_DUE and self.past_due_since:
            return self.past_due_since + timedelta(
                days=settings.BILLING_PAST_DUE_GRACE_DAYS
            ) > timezone.now()
        return (
            self.status == self.Status.TRIALING
            and self.trial_ends_at is not None
            and self.trial_ends_at > timezone.now()
        )

    def __str__(self):
        return f"{self.organization} - {self.get_plan_display()}"


class WebhookEvent(models.Model):
    provider_event_id = models.CharField(max_length=160, unique=True)
    event_type = models.CharField(max_length=120)
    payload = models.JSONField(default=dict)
    occurred_at = models.DateTimeField(null=True, blank=True)
    processing_error = models.TextField(blank=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "evento de pago"
        verbose_name_plural = "eventos de pago"

    def __str__(self):
        return f"{self.event_type}: {self.provider_event_id}"


class BillingNotification(models.Model):
    subscription = models.ForeignKey(
        Subscription, on_delete=models.CASCADE, related_name="notifications"
    )
    notification_type = models.CharField(max_length=60)
    reference_date = models.DateField()
    sent_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("subscription", "notification_type", "reference_date"),
                name="unique_billing_notification",
            )
        ]
