import uuid
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class Organization(models.Model):
    class BusinessType(models.TextChoices):
        AUTO_REPAIR = "auto_repair", _("Taller / Oficina")
        OFFICE = "office", _("Oficina administrativa")
        PERSONAL = "personal_business", _("Negocio personal")
        SERVICES = "services", _("Servicios profesionales")
        RETAIL = "retail", _("Comercio")
        OTHER = "other", _("Otro negocio")

    class Language(models.TextChoices):
        SPANISH = "es", _("Español")
        PORTUGUESE_BR = "pt-br", _("Português do Brasil")

    class Country(models.TextChoices):
        ARGENTINA = "AR", _("Argentina")
        BOLIVIA = "BO", _("Bolivia")
        BRAZIL = "BR", _("Brasil")
        CHILE = "CL", _("Chile")
        COLOMBIA = "CO", _("Colombia")
        COSTA_RICA = "CR", _("Costa Rica")
        DOMINICAN_REPUBLIC = "DO", _("República Dominicana")
        ECUADOR = "EC", _("Ecuador")
        EL_SALVADOR = "SV", _("El Salvador")
        GUATEMALA = "GT", _("Guatemala")
        HONDURAS = "HN", _("Honduras")
        MEXICO = "MX", _("México")
        NICARAGUA = "NI", _("Nicaragua")
        PANAMA = "PA", _("Panamá")
        PARAGUAY = "PY", _("Paraguay")
        PERU = "PE", _("Perú")
        URUGUAY = "UY", _("Uruguay")
        VENEZUELA = "VE", _("Venezuela")
        OTHER = "OT", _("Otro")

    class Currency(models.TextChoices):
        ARS = "ARS", "ARS"
        BOB = "BOB", "BOB"
        BRL = "BRL", "BRL"
        CLP = "CLP", "CLP"
        COP = "COP", "COP"
        CRC = "CRC", "CRC"
        DOP = "DOP", "DOP"
        GTQ = "GTQ", "GTQ"
        HNL = "HNL", "HNL"
        MXN = "MXN", "MXN"
        NIO = "NIO", "NIO"
        PAB = "PAB", "PAB"
        PEN = "PEN", "PEN"
        PYG = "PYG", "PYG"
        USD = "USD", "USD"
        UYU = "UYU", "UYU"
        VES = "VES", "VES"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField("nombre", max_length=160)
    business_type = models.CharField(
        _("tipo de negocio"),
        max_length=40,
        choices=BusinessType.choices,
        default=BusinessType.AUTO_REPAIR,
    )
    language = models.CharField(
        _("idioma"),
        max_length=10,
        choices=Language.choices,
        default=Language.SPANISH,
    )
    slug = models.SlugField(unique=True)
    legal_name = models.CharField("razón social", max_length=180, blank=True)
    tax_id = models.CharField("documento fiscal", max_length=40, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField("teléfono", max_length=40, blank=True)
    address = models.TextField("dirección", blank=True)
    city = models.CharField("ciudad", max_length=100, blank=True)
    country = models.CharField(
        "país", max_length=2, choices=Country.choices, default=Country.BRAZIL
    )
    currency = models.CharField(
        "moneda", max_length=3, choices=Currency.choices, default=Currency.BRL
    )
    timezone = models.CharField(
        "zona horaria", max_length=64, default="America/Sao_Paulo"
    )
    quote_prefix = models.CharField(
        "prefijo de presupuesto",
        max_length=12,
        default="PRES",
        validators=[
            RegexValidator(
                regex=r"^[A-Za-z0-9-]+$",
                message=_("Usa únicamente letras, números y guiones."),
            )
        ],
    )
    default_quote_terms = models.TextField("condiciones del presupuesto", blank=True)
    default_warranty_text = models.TextField("garantía", blank=True)
    default_payment_terms = models.TextField("condiciones de pago", blank=True)
    default_footer = models.CharField("pie de documento", max_length=240, blank=True)
    public_quote_valid_days = models.PositiveSmallIntegerField(
        "vigencia del enlace público en días", default=90
    )
    logo_data = models.BinaryField(null=True, blank=True, editable=False)
    logo_content_type = models.CharField(max_length=40, blank=True, editable=False)
    logo_filename = models.CharField(max_length=180, blank=True, editable=False)
    logo_updated_at = models.DateTimeField(null=True, blank=True, editable=False)
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

    def clean(self):
        super().clean()
        try:
            ZoneInfo(self.timezone)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValidationError({"timezone": _("Selecciona una zona horaria válida.")})

    def save(self, *args, **kwargs):
        self.quote_prefix = (self.quote_prefix or "PRES").strip().upper()
        super().save(*args, **kwargs)

    @property
    def has_logo(self):
        return bool(self.logo_data and self.logo_content_type == "image/png")


class Membership(models.Model):
    class Role(models.TextChoices):
        OWNER = "owner", _("Propietario")
        ADMIN = "admin", _("Administrador")
        MEMBER = "member", _("Colaborador")

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

    @property
    def can_manage_business(self):
        return self.role in {self.Role.OWNER, self.Role.ADMIN}

    @property
    def is_owner(self):
        return self.role == self.Role.OWNER


class OrganizationInvitation(models.Model):
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="invitations"
    )
    email = models.EmailField()
    role = models.CharField(
        max_length=20, choices=Membership.Role.choices, default=Membership.Role.MEMBER
    )
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="organization_invitations_created",
    )
    expires_at = models.DateTimeField()
    accepted_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [models.Index(fields=("organization", "email"))]

    @property
    def is_valid(self):
        return (
            self.accepted_at is None
            and self.revoked_at is None
            and self.expires_at > timezone.now()
        )

    def __str__(self):
        return f"{self.email} -> {self.organization}"


class OrganizationEvent(models.Model):
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="events"
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="organization_events",
    )
    event_type = models.CharField(max_length=80)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [models.Index(fields=("organization", "created_at"))]


class OrganizationDeletionRequest(models.Model):
    organization = models.OneToOneField(
        Organization, on_delete=models.CASCADE, related_name="deletion_request"
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="organization_deletion_requests",
    )
    execute_after = models.DateTimeField()
    cancelled_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("execute_after",)

    @property
    def is_pending(self):
        return self.cancelled_at is None
