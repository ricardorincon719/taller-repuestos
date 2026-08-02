import json
import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseBadRequest, JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from apps.organizations.models import Membership
from apps.organizations.services import get_request_membership

from .client import PaddleAPIError, create_customer_portal_session
from .models import Subscription
from .services import (
    InvalidWebhookSignature,
    process_paddle_webhook,
    verify_paddle_signature,
)


logger = logging.getLogger(__name__)


@login_required
def billing_status(request):
    membership = get_request_membership(request)
    try:
        subscription = membership.organization.subscription
    except Subscription.DoesNotExist:
        subscription = None
    price_id = settings.PADDLE_PROFESSIONAL_PRICE_ID or settings.PADDLE_STARTER_PRICE_ID
    return render(
        request,
        "billing/status.html",
        {
            "organization": membership.organization,
            "membership": membership,
            "subscription": subscription,
            "paddle_enabled": settings.PADDLE_ENABLED,
            "paddle_environment": settings.PADDLE_ENVIRONMENT,
            "paddle_client_token": settings.PADDLE_CLIENT_TOKEN,
            "paddle_price_id": price_id,
            "paddle_locale": "pt" if membership.organization.language == "pt-br" else "es",
            "paddle_preview_enabled": bool(
                settings.PADDLE_ENABLED
                and settings.PADDLE_CLIENT_TOKEN
                and price_id
            ),
            "can_checkout": bool(
                settings.PADDLE_ENABLED
                and price_id
                and membership.role == Membership.Role.OWNER
                and (
                    subscription is None
                    or (
                        not subscription.provider_subscription_id
                        and subscription.status != Subscription.Status.ACTIVE
                    )
                    or subscription.status == Subscription.Status.CANCELLED
                )
            ),
        },
    )


@login_required
@require_POST
def billing_portal(request):
    membership = get_request_membership(request)
    if membership.role != Membership.Role.OWNER:
        return HttpResponseBadRequest("Solo el propietario puede administrar la suscripción.")
    try:
        subscription = membership.organization.subscription
    except Subscription.DoesNotExist:
        messages.error(request, "Todavía no hay una suscripción asociada.")
        return redirect("billing-status")
    if not subscription.provider_customer_id:
        messages.error(request, "Paddle todavía no confirmó el cliente de pago.")
        return redirect("billing-status")
    try:
        portal_url = create_customer_portal_session(subscription)
    except PaddleAPIError:
        logger.exception("Could not create Paddle customer portal session")
        messages.error(request, "El portal de pagos no está disponible. Inténtalo de nuevo.")
        return redirect("billing-status")
    return redirect(portal_url)


@csrf_exempt
@require_POST
def paddle_webhook(request):
    try:
        verify_paddle_signature(
            request.body, request.headers.get("Paddle-Signature", "")
        )
    except InvalidWebhookSignature:
        logger.warning("Rejected Paddle webhook with invalid signature")
        return JsonResponse({"error": "invalid signature"}, status=400)
    try:
        event = process_paddle_webhook(request.body)
    except (json.JSONDecodeError, KeyError, ValueError):
        logger.exception("Rejected malformed Paddle webhook")
        return JsonResponse({"error": "invalid payload"}, status=400)
    except Exception:
        logger.exception("Paddle webhook processing failed")
        return JsonResponse({"error": "processing failed"}, status=500)
    return JsonResponse({"status": "ok", "event_id": event.provider_event_id})
