from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from apps.organizations.services import get_current_membership

from .models import Subscription


@login_required
def billing_status(request):
    membership = get_current_membership(request.user)
    try:
        subscription = membership.organization.subscription
    except Subscription.DoesNotExist:
        subscription = None
    return render(
        request,
        "billing/status.html",
        {
            "organization": membership.organization,
            "subscription": subscription,
        },
    )
