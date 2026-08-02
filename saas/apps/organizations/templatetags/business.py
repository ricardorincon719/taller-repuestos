from django import template

from apps.organizations.formatting import format_money
from apps.organizations.models import Organization


register = template.Library()


@register.filter
def money(value, organization_or_currency=None):
    currency = getattr(organization_or_currency, "currency", organization_or_currency)
    return format_money(value, currency or "BRL")


@register.filter
def business_type_label(value):
    try:
        return Organization.BusinessType(value).label
    except ValueError:
        return value
