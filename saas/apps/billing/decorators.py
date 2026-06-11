from functools import wraps

from django.shortcuts import redirect

from apps.organizations.services import get_current_membership

from .models import Subscription


def subscription_required(view_func):
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        membership = get_current_membership(request.user)
        try:
            subscription = membership.organization.subscription
        except Subscription.DoesNotExist:
            return redirect("billing-status")
        if not subscription.allows_access:
            return redirect("billing-status")
        request.current_membership = membership
        request.current_subscription = subscription
        return view_func(request, *args, **kwargs)

    return wrapped
