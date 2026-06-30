from django import forms
from django.utils.translation import gettext_lazy as _

from .models import Customer, Vehicle


class CustomerForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = ("name", "phone", "email", "tax_id", "address", "notes")
        labels = {
            "name": _("Nombre"),
            "phone": _("Teléfono"),
            "email": _("Email"),
            "tax_id": _("Documento fiscal"),
            "address": _("Dirección"),
            "notes": _("Notas"),
        }
        widgets = {
            "address": forms.Textarea(attrs={"rows": 2}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }


class VehicleForm(forms.ModelForm):
    class Meta:
        model = Vehicle
        fields = ("license_plate", "make", "model", "year", "notes")
        labels = {
            "license_plate": _("Matrícula"),
            "make": _("Marca"),
            "model": _("Modelo"),
            "year": _("Año"),
            "notes": _("Notas"),
        }
        widgets = {"notes": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, organization, **kwargs):
        super().__init__(*args, **kwargs)
        self.organization = organization

    def clean_license_plate(self):
        license_plate = self.cleaned_data["license_plate"].strip().upper()
        if not license_plate:
            return license_plate
        duplicate = Vehicle.objects.filter(
            organization=self.organization,
            license_plate=license_plate,
        ).exclude(pk=self.instance.pk)
        if duplicate.exists():
            raise forms.ValidationError(_("Ya existe un vehículo con esta matrícula."))
        return license_plate
