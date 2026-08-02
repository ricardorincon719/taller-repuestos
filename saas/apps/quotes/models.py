import uuid
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.customers.models import Customer, Vehicle
from apps.organizations.models import Organization


class QuoteQuerySet(models.QuerySet):
    def for_organization(self, organization):
        return self.filter(organization=organization)


class Quote(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", _("Borrador")
        SENT = "sent", _("Enviado")
        APPROVED = "approved", _("Aprobado")
        INVOICED = "invoiced", _("Facturado")
        REJECTED = "rejected", _("Rechazado")
        CANCELLED = "cancelled", _("Cancelado")

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="quotes",
    )
    share_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    public_access_enabled = models.BooleanField(default=False)
    share_expires_at = models.DateTimeField(null=True, blank=True)
    number = models.PositiveBigIntegerField()
    number_prefix = models.CharField(max_length=12, blank=True)
    currency = models.CharField(max_length=3, default="BRL")
    source_quote = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="duplicates",
    )
    legacy_source = models.CharField(max_length=40, blank=True)
    legacy_id = models.CharField(max_length=80, blank=True)
    customer = models.ForeignKey(
        Customer,
        on_delete=models.PROTECT,
        related_name="quotes",
    )
    vehicle = models.ForeignKey(
        Vehicle,
        on_delete=models.PROTECT,
        related_name="quotes",
        null=True,
        blank=True,
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    notes = models.TextField("notas", blank=True)
    labor_amount = models.DecimalField(
        "mano de obra",
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    items_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        editable=False,
    )
    discount_amount = models.DecimalField(
        "descuento",
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    total_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        editable=False,
    )
    valid_until = models.DateField("válido hasta", null=True, blank=True)
    issue_snapshot = models.JSONField(default=dict, blank=True)
    issued_at = models.DateTimeField(null=True, blank=True)
    is_archived = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_quotes",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = QuoteQuerySet.as_manager()

    class Meta:
        ordering = ("-created_at",)
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "number"),
                name="unique_quote_number_per_organization",
            ),
            models.UniqueConstraint(
                fields=("organization", "legacy_source", "legacy_id"),
                condition=~models.Q(legacy_id=""),
                name="unique_legacy_quote_per_organization",
            ),
        ]
        indexes = [
            models.Index(fields=("organization", "status")),
            models.Index(fields=("organization", "created_at")),
        ]
        verbose_name = "presupuesto"
        verbose_name_plural = "presupuestos"

    @property
    def display_number(self):
        prefix = self.number_prefix or self.organization.quote_prefix
        return f"{prefix}-{self.number:06d}"

    @property
    def is_editable(self):
        return self.status == self.Status.DRAFT and self.issued_at is None

    @property
    def public_is_available(self):
        return (
            self.public_access_enabled
            and not self.is_archived
            and (self.share_expires_at is None or self.share_expires_at > timezone.now())
        )

    def can_transition_to(self, new_status):
        transitions = {
            self.Status.DRAFT: {self.Status.SENT, self.Status.CANCELLED},
            self.Status.SENT: {
                self.Status.APPROVED,
                self.Status.REJECTED,
                self.Status.CANCELLED,
            },
            self.Status.APPROVED: {self.Status.INVOICED, self.Status.CANCELLED},
            self.Status.INVOICED: set(),
            self.Status.REJECTED: set(),
            self.Status.CANCELLED: set(),
        }
        return new_status == self.status or new_status in transitions.get(self.status, set())

    def recalculate_totals(self, save=True):
        items_amount = sum(
            (
                item.total_amount
                for item in self.items.model.objects.filter(quote_id=self.pk).only(
                    "quantity", "unit_price"
                )
            ),
            Decimal("0.00"),
        )
        self.items_amount = items_amount
        self.total_amount = max(
            self.labor_amount + items_amount - self.discount_amount,
            Decimal("0.00"),
        )
        if save:
            self.save(update_fields=("items_amount", "total_amount", "updated_at"))
        return self.total_amount

    def clean(self):
        super().clean()
        if self.customer_id and self.customer.organization_id != self.organization_id:
            raise ValidationError(
                {"customer": _("El cliente debe pertenecer al mismo negocio.")}
            )
        if self.vehicle_id:
            if self.vehicle.organization_id != self.organization_id:
                raise ValidationError(
                    {"vehicle": _("El vehículo debe pertenecer al mismo negocio.")}
                )
            if self.vehicle.customer_id != self.customer_id:
                raise ValidationError(
                    {"vehicle": _("El vehículo debe pertenecer al cliente seleccionado.")}
                )

    def __str__(self):
        return f"{self.display_number} - {self.customer}"


class QuoteItem(models.Model):
    quote = models.ForeignKey(Quote, on_delete=models.CASCADE, related_name="items")
    description = models.CharField("descripción", max_length=240)
    quantity = models.DecimalField(
        "cantidad",
        max_digits=10,
        decimal_places=2,
        default=Decimal("1.00"),
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    unit_price = models.DecimalField(
        "precio unitario",
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    position = models.PositiveSmallIntegerField("posición", default=0)

    class Meta:
        ordering = ("position", "id")
        verbose_name = "ítem de presupuesto"
        verbose_name_plural = "ítems de presupuesto"

    @property
    def total_amount(self):
        return self.quantity * self.unit_price

    def __str__(self):
        return self.description


class QuoteEvent(models.Model):
    EVENT_LABELS = {
        "quote.created": _("Presupuesto creado"),
        "quote.updated": _("Borrador actualizado"),
        "quote.status_changed": _("Estado actualizado"),
        "quote.duplicated": _("Presupuesto duplicado"),
        "quote.share_renewed": _("Enlace renovado"),
        "quote.share_revoked": _("Enlace revocado"),
        "quote.archived": _("Presupuesto archivado"),
        "quote.restored": _("Presupuesto restaurado"),
    }
    quote = models.ForeignKey(Quote, on_delete=models.CASCADE, related_name="events")
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="quote_events",
    )
    event_type = models.CharField(max_length=80)
    from_status = models.CharField(max_length=20, blank=True)
    to_status = models.CharField(max_length=20, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [models.Index(fields=("quote", "created_at"))]

    def __str__(self):
        return f"{self.quote.display_number}: {self.event_type}"

    @property
    def event_label(self):
        return self.EVENT_LABELS.get(self.event_type, self.event_type)
