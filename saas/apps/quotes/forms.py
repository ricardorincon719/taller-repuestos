from django import forms
from django.forms import inlineformset_factory

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
            self.add_error("customer", "Cliente inválido para este taller.")
        if vehicle:
            if vehicle.organization_id != self.organization.id:
                self.add_error("vehicle", "Vehículo inválido para este taller.")
            elif customer and vehicle.customer_id != customer.id:
                self.add_error("vehicle", "El vehículo no pertenece al cliente.")
        return cleaned_data


QuoteItemFormSet = inlineformset_factory(
    Quote,
    QuoteItem,
    fields=("description", "quantity", "unit_price"),
    extra=1,
    can_delete=True,
)
