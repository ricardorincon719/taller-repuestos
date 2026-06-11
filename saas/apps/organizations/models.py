import uuid

from django.conf import settings
from django.db import models


class Organization(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField("nombre", max_length=160)
    slug = models.SlugField(unique=True)
    tax_id = models.CharField("documento fiscal", max_length=40, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField("teléfono", max_length=40, blank=True)
    address = models.TextField("dirección", blank=True)
    quote_prefix = models.CharField(
        "prefijo de presupuesto", max_length=12, default="PRES"
    )
    next_quote_number = models.PositiveBigIntegerField(default=1)
    is_active = models.BooleanField("activo", default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("name",)
        verbose_name = "organización"
        verbose_name_plural = "organizaciones"

    def __str__(self):
        return self.name


class Membership(models.Model):
    class Role(models.TextChoices):
        OWNER = "owner", "Propietario"
        ADMIN = "admin", "Administrador"
        MEMBER = "member", "Colaborador"

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="organization_memberships",
    )
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.MEMBER)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "user"),
                name="unique_organization_membership",
            )
        ]
        ordering = ("organization__name", "user__email")
        verbose_name = "membresía"
        verbose_name_plural = "membresías"

    def __str__(self):
        return f"{self.user} - {self.organization} ({self.get_role_display()})"
