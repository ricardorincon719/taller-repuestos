import uuid
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
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
    number = models.PositiveBigIntegerField()
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
        return f"{self.organization.quote_prefix}-{self.number:06d}"

    def recalculate_totals(self, save=True):
        items_amount = sum(
            (item.total_amount for item in self.items.all()),
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
