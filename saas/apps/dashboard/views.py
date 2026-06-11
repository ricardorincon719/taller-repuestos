from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.db.models.fields import DecimalField
from django.shortcuts import render

from apps.billing.decorators import subscription_required
from apps.organizations.services import get_current_membership
from apps.quotes.models import Quote


@login_required
@subscription_required
def dashboard(request):
    membership = get_current_membership(request.user)
    organization = membership.organization
    quotes = Quote.objects.for_organization(organization)
    money_field = DecimalField(max_digits=12, decimal_places=2)
    metrics = quotes.aggregate(
        total_quotes=Count("id"),
        total_invoiced=Coalesce(
            Sum("total_amount", filter=Q(status=Quote.Status.INVOICED)),
            Value(0),
            output_field=money_field,
        ),
        total_pending=Coalesce(
            Sum(
                "total_amount",
                filter=Q(status__in=(Quote.Status.SENT, Quote.Status.APPROVED)),
            ),
            Value(0),
            output_field=money_field,
        ),
    )
    return render(
        request,
        "dashboard/index.html",
        {
            "organization": organization,
            "membership": membership,
            "metrics": metrics,
            "recent_quotes": quotes.select_related("customer", "vehicle")[:8],
        },
    )
