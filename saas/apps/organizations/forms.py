from django import forms
from django.utils.translation import gettext_lazy as _

from .models import Organization


class OrganizationProfileForm(forms.ModelForm):
    class Meta:
        model = Organization
        fields = (
            "name",
            "business_type",
            "language",
            "email",
            "phone",
            "address",
            "tax_id",
            "quote_prefix",
        )
        labels = {
            "name": _("Nombre comercial"),
            "business_type": _("Tipo de negocio"),
            "language": _("Idioma del sistema"),
            "email": _("Email comercial"),
            "phone": _("Teléfono / WhatsApp"),
            "address": _("Dirección"),
            "tax_id": _("Documento fiscal"),
            "quote_prefix": _("Prefijo de documentos"),
        }
        help_texts = {
            "language": _(
                "Este idioma se aplica al panel de esta cuenta y prepara los documentos del negocio."
            ),
            "quote_prefix": _("Ejemplo: PRES, COT, ORC."),
        }
        widgets = {
            "address": forms.Textarea(attrs={"rows": 3}),
        }
