from django import forms
from django.forms import inlineformset_factory
from django.utils.translation import gettext_lazy as _

from apps.customers.models import Customer, Vehicle

from .models import Quote, QuoteItem


class QuoteForm(forms.ModelForm):
    class Meta:
        model = Quote
        fields = (
            "customer",
            "vehicle",
            "status",
            "labor_amount",
            "discount_amount",
            "valid_until",
            "notes",
        )
        widgets = {
            "valid_until": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }
        labels = {
            "customer": _("Cliente"),
            "vehicle": _("Vehículo"),
            "status": _("Estado"),
            "labor_amount": _("Mano de obra"),
            "discount_amount": _("Descuento"),
            "valid_until": _("Válido hasta"),
            "notes": _("Notas"),
        }

    def __init__(self, *args, organization, **kwargs):
        super().__init__(*args, **kwargs)
        self.organization = organization
        self.fields["customer"].queryset = Customer.objects.for_organization(
            organization
        ).filter(is_active=True)
        self.fields["vehicle"].queryset = Vehicle.objects.for_organization(
            organization
        ).filter(is_active=True).select_related("customer")

    def clean(self):
        cleaned_data = super().clean()
        customer = cleaned_data.get("customer")
        vehicle = cleaned_data.get("vehicle")
        if customer and customer.organization_id != self.organization.id:
            self.add_error("customer", _("Cliente inválido para este negocio."))
        if vehicle:
            if vehicle.organization_id != self.organization.id:
                self.add_error("vehicle", _("Vehículo inválido para este negocio."))
            elif customer and vehicle.customer_id != customer.id:
                self.add_error("vehicle", _("El vehículo no pertenece al cliente."))
        return cleaned_data


QuoteItemFormSet = inlineformset_factory(
    Quote,
    QuoteItem,
    fields=("description", "quantity", "unit_price"),
    extra=1,
    can_delete=False,
    widgets={
        "description": forms.TextInput(attrs={"placeholder": _("Ej. Filtro de aceite")}),
        "quantity": forms.NumberInput(attrs={"step": "0.01", "min": "0.01"}),
        "unit_price": forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
    },
    labels={
        "description": _("Descripción"),
        "quantity": _("Cantidad"),
        "unit_price": _("Precio unitario"),
    },
)
