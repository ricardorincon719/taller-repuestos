from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.organizations.models import Organization


class CustomerQuerySet(models.QuerySet):
    def for_organization(self, organization):
        return self.filter(organization=organization)


class Customer(models.Model):
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="customers",
    )
    name = models.CharField("nombre", max_length=160)
    email = models.EmailField(blank=True)
    phone = models.CharField("teléfono", max_length=40, blank=True)
    tax_id = models.CharField("documento fiscal", max_length=40, blank=True)
    address = models.TextField("dirección", blank=True)
    notes = models.TextField("notas", blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = CustomerQuerySet.as_manager()

    class Meta:
        ordering = ("name",)
        indexes = [models.Index(fields=("organization", "name"))]
        verbose_name = "cliente"
        verbose_name_plural = "clientes"

    def __str__(self):
        return self.name


class VehicleQuerySet(models.QuerySet):
    def for_organization(self, organization):
        return self.filter(organization=organization)


class Vehicle(models.Model):
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="vehicles",
    )
    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name="vehicles",
    )
    license_plate = models.CharField("matrícula", max_length=20, blank=True)
    make = models.CharField("marca", max_length=80, blank=True)
    model = models.CharField("modelo", max_length=80, blank=True)
    year = models.PositiveSmallIntegerField("año", null=True, blank=True)
    notes = models.TextField("notas", blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = VehicleQuerySet.as_manager()

    class Meta:
        ordering = ("license_plate", "make", "model")
        indexes = [models.Index(fields=("organization", "license_plate"))]
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "license_plate"),
                condition=~models.Q(license_plate=""),
                name="unique_vehicle_plate_per_organization",
            )
        ]
        verbose_name = "vehículo"
        verbose_name_plural = "vehículos"

    def clean(self):
        super().clean()
        if self.customer_id and self.customer.organization_id != self.organization_id:
            raise ValidationError(
                {"customer": _("El cliente debe pertenecer al mismo negocio.")}
            )

    def __str__(self):
        description = " ".join(part for part in (self.make, self.model) if part)
        return self.license_plate or description or _("Vehículo #%(pk)s") % {"pk": self.pk}
