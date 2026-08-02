from django import forms
from django.contrib.auth import password_validation
from django.utils.translation import gettext_lazy as _
from PIL import Image, UnidentifiedImageError

from .models import Membership, Organization


TIMEZONE_CHOICES = (
    ("America/Argentina/Buenos_Aires", "Argentina — Buenos Aires"),
    ("America/La_Paz", "Bolivia — La Paz"),
    ("America/Sao_Paulo", "Brasil — São Paulo"),
    ("America/Santiago", "Chile — Santiago"),
    ("America/Bogota", "Colombia — Bogotá"),
    ("America/Costa_Rica", "Costa Rica"),
    ("America/Santo_Domingo", "República Dominicana"),
    ("America/Guayaquil", "Ecuador — Guayaquil"),
    ("America/El_Salvador", "El Salvador"),
    ("America/Guatemala", "Guatemala"),
    ("America/Tegucigalpa", "Honduras — Tegucigalpa"),
    ("America/Mexico_City", "México — Ciudad de México"),
    ("America/Managua", "Nicaragua — Managua"),
    ("America/Panama", "Panamá"),
    ("America/Asuncion", "Paraguay — Asunción"),
    ("America/Lima", "Perú — Lima"),
    ("America/Montevideo", "Uruguay — Montevideo"),
    ("America/Caracas", "Venezuela — Caracas"),
)


class OrganizationProfileForm(forms.ModelForm):
    logo = forms.FileField(
        label=_("Logo PNG"),
        required=False,
        help_text=_("PNG de hasta 1 MB y 1200×600 píxeles."),
    )
    remove_logo = forms.BooleanField(label=_("Eliminar logo actual"), required=False)

    class Meta:
        model = Organization
        fields = (
            "name",
            "legal_name",
            "business_type",
            "language",
            "email",
            "phone",
            "address",
            "city",
            "country",
            "currency",
            "timezone",
            "tax_id",
            "quote_prefix",
            "default_quote_terms",
            "default_warranty_text",
            "default_payment_terms",
            "default_footer",
            "public_quote_valid_days",
        )
        labels = {
            "name": _("Nombre comercial"),
            "legal_name": _("Razón social"),
            "business_type": _("Tipo de negocio"),
            "language": _("Idioma del sistema"),
            "email": _("Email comercial"),
            "phone": _("Teléfono / WhatsApp"),
            "address": _("Dirección"),
            "city": _("Ciudad"),
            "country": _("País"),
            "currency": _("Moneda"),
            "timezone": _("Zona horaria"),
            "tax_id": _("Documento fiscal"),
            "quote_prefix": _("Prefijo de documentos"),
            "default_quote_terms": _("Condiciones predeterminadas"),
            "default_warranty_text": _("Garantía predeterminada"),
            "default_payment_terms": _("Condiciones de pago"),
            "default_footer": _("Pie del documento"),
            "public_quote_valid_days": _("Vigencia del enlace público (días)"),
        }
        help_texts = {
            "language": _(
                "Este idioma se aplica al panel de esta cuenta y prepara los documentos del negocio."
            ),
            "quote_prefix": _("Ejemplo: PRES, COT, ORC."),
            "public_quote_valid_days": _("Después de este plazo el enlace deja de abrir."),
        }
        widgets = {
            "address": forms.Textarea(attrs={"rows": 3}),
            "default_quote_terms": forms.Textarea(attrs={"rows": 3}),
            "default_warranty_text": forms.Textarea(attrs={"rows": 3}),
            "default_payment_terms": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["timezone"].widget = forms.Select(choices=TIMEZONE_CHOICES)

    def clean_logo(self):
        upload = self.cleaned_data.get("logo")
        if not upload:
            return upload
        if upload.size > 1024 * 1024:
            raise forms.ValidationError(_("El logo no puede superar 1 MB."))
        data = upload.read()
        upload.seek(0)
        if len(data) < 24 or data[:8] != b"\x89PNG\r\n\x1a\n":
            raise forms.ValidationError(_("El archivo debe ser una imagen PNG válida."))
        try:
            image = Image.open(upload)
            image.verify()
            if image.format != "PNG":
                raise forms.ValidationError(_("El archivo debe ser una imagen PNG válida."))
            width, height = image.size
        except (UnidentifiedImageError, OSError, SyntaxError):
            raise forms.ValidationError(_("El archivo debe ser una imagen PNG válida."))
        finally:
            upload.seek(0)
        if width < 1 or height < 1 or width > 1200 or height > 600:
            raise forms.ValidationError(_("El logo debe medir como máximo 1200×600 píxeles."))
        return upload

    def clean_public_quote_valid_days(self):
        days = self.cleaned_data["public_quote_valid_days"]
        if not 1 <= days <= 365:
            raise forms.ValidationError(_("La vigencia debe estar entre 1 y 365 días."))
        return days


class InvitationForm(forms.Form):
    email = forms.EmailField(label="Email")
    role = forms.ChoiceField(
        label=_("Rol"),
        choices=(
            (Membership.Role.ADMIN, _("Administrador")),
            (Membership.Role.MEMBER, _("Colaborador")),
        ),
    )

    def clean_email(self):
        return self.cleaned_data["email"].strip().lower()


class InvitationAcceptanceForm(forms.Form):
    first_name = forms.CharField(label=_("Nombre"), max_length=150)
    last_name = forms.CharField(label=_("Apellido"), max_length=150, required=False)
    password1 = forms.CharField(label=_("Contraseña"), widget=forms.PasswordInput)
    password2 = forms.CharField(label=_("Confirmar contraseña"), widget=forms.PasswordInput)

    def clean(self):
        data = super().clean()
        if data.get("password1") and data.get("password1") != data.get("password2"):
            self.add_error("password2", _("Las contraseñas no coinciden."))
        if data.get("password1"):
            password_validation.validate_password(data["password1"])
        return data


class MemberRoleForm(forms.Form):
    role = forms.ChoiceField(label=_("Rol"), choices=Membership.Role.choices)
    is_active = forms.BooleanField(label=_("Acceso activo"), required=False)


class OrganizationDeletionForm(forms.Form):
    organization_name = forms.CharField(label=_("Escribe el nombre del negocio"))
    password = forms.CharField(label=_("Tu contraseña"), widget=forms.PasswordInput)

    def __init__(self, *args, user, organization, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.organization = organization

    def clean_organization_name(self):
        value = self.cleaned_data["organization_name"].strip()
        if value.casefold() != self.organization.name.casefold():
            raise forms.ValidationError(_("El nombre no coincide."))
        return value

    def clean_password(self):
        password = self.cleaned_data["password"]
        if not self.user.check_password(password):
            raise forms.ValidationError(_("Contraseña incorrecta."))
        return password
