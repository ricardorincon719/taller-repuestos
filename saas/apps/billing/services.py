import hashlib
import hmac
import json
import logging
import time
from datetime import datetime, timezone as datetime_timezone

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.utils.translation import gettext as _

from apps.organizations.models import Organization

from .models import Subscription, WebhookEvent


logger = logging.getLogger(__name__)


class InvalidWebhookSignature(ValueError):
    pass


def verify_paddle_signature(raw_body, signature_header):
    if not settings.PADDLE_WEBHOOK_SECRET:
        raise InvalidWebhookSignature("Webhook secret is not configured")
    values = {}
    for part in (signature_header or "").split(";"):
        key, separator, value = part.partition("=")
        if separator and key and value:
            values.setdefault(key, []).append(value)
    try:
        timestamp = int(values["ts"][0])
        signatures = values["h1"]
    except (KeyError, IndexError, ValueError) as exc:
        raise InvalidWebhookSignature("Malformed Paddle-Signature") from exc
    if abs(int(time.time()) - timestamp) > settings.PADDLE_WEBHOOK_TOLERANCE:
        raise InvalidWebhookSignature("Expired webhook signature")
    signed_payload = str(timestamp).encode() + b":" + raw_body
    expected = hmac.new(
        settings.PADDLE_WEBHOOK_SECRET.encode(), signed_payload, hashlib.sha256
    ).hexdigest()
    if not any(hmac.compare_digest(expected, candidate) for candidate in signatures):
        raise InvalidWebhookSignature("Invalid webhook signature")


def _event_datetime(value):
    parsed = parse_datetime(value or "")
    if parsed and timezone.is_naive(parsed):
        return timezone.make_aware(parsed, datetime_timezone.utc)
    return parsed


def _subscription_for_payload(data):
    provider_subscription_id = data.get("id", "")
    provider_customer_id = data.get("customer_id", "")
    subscription = Subscription.objects.select_for_update().filter(
        provider_subscription_id=provider_subscription_id
    ).first()
    if subscription is None and provider_customer_id:
        subscription = Subscription.objects.select_for_update().filter(
            provider_customer_id=provider_customer_id
        ).first()
    if subscription is None:
        organization_id = (data.get("custom_data") or {}).get("organization_id")
        if organization_id:
            try:
                organization = Organization.objects.filter(pk=organization_id).first()
            except (ValidationError, ValueError):
                organization = None
            if organization:
                subscription, _created = Subscription.objects.select_for_update().get_or_create(
                    organization=organization
                )
    return subscription


def _mapped_status(provider_status):
    return {
        "trialing": Subscription.Status.TRIALING,
        "active": Subscription.Status.ACTIVE,
        "past_due": Subscription.Status.PAST_DUE,
        "paused": Subscription.Status.PAUSED,
        "canceled": Subscription.Status.CANCELLED,
        "cancelled": Subscription.Status.CANCELLED,
    }.get(provider_status)


def _plan_for_price(price_id):
    if price_id == settings.PADDLE_PROFESSIONAL_PRICE_ID:
        return Subscription.Plan.PROFESSIONAL
    if price_id == settings.PADDLE_STARTER_PRICE_ID:
        return Subscription.Plan.STARTER
    return None


@transaction.atomic
def process_paddle_webhook(raw_body):
    payload = json.loads(raw_body)
    event_id = payload["event_id"]
    event_type = payload["event_type"]
    occurred_at = _event_datetime(payload.get("occurred_at"))
    event, created = WebhookEvent.objects.select_for_update().get_or_create(
        provider_event_id=event_id,
        defaults={
            "event_type": event_type,
            "payload": payload,
            "occurred_at": occurred_at,
        },
    )
    if not created and event.processed_at:
        return event
    event.event_type = event_type
    event.payload = payload
    event.occurred_at = occurred_at
    try:
        if event_type in {
            "subscription.created",
            "subscription.updated",
            "subscription.canceled",
        }:
            data = payload.get("data") or {}
            subscription = _subscription_for_payload(data)
            if subscription is None:
                raise ValueError("No organization matches the Paddle subscription")
            if (
                occurred_at
                and subscription.provider_last_event_at
                and occurred_at < subscription.provider_last_event_at
            ):
                event.processed_at = timezone.now()
                event.processing_error = ""
                event.save(
                    update_fields=(
                        "event_type", "payload", "occurred_at", "processed_at", "processing_error"
                    )
                )
                return event
            old_status = subscription.status
            status = _mapped_status(data.get("status"))
            if status:
                subscription.status = status
            subscription.provider_customer_id = data.get(
                "customer_id", subscription.provider_customer_id
            )
            subscription.provider_subscription_id = data.get(
                "id", subscription.provider_subscription_id
            )
            items = data.get("items") or []
            price_id = ""
            if items:
                price_id = (items[0].get("price") or {}).get("id", "")
            if price_id:
                subscription.provider_price_id = price_id
                plan = _plan_for_price(price_id)
                if plan:
                    subscription.plan = plan
            billing_period = data.get("current_billing_period") or {}
            subscription.current_period_ends_at = _event_datetime(
                billing_period.get("ends_at")
            )
            if subscription.status == Subscription.Status.TRIALING:
                subscription.trial_ends_at = _event_datetime(data.get("next_billed_at"))
            if subscription.status == Subscription.Status.PAST_DUE:
                subscription.past_due_since = subscription.past_due_since or occurred_at or timezone.now()
            else:
                subscription.past_due_since = None
            scheduled_change = data.get("scheduled_change") or {}
            subscription.cancel_at_period_end = scheduled_change.get("action") == "cancel"
            subscription.provider_last_event_at = occurred_at or timezone.now()
            subscription.save()
            if old_status != subscription.status:
                transaction.on_commit(
                    lambda: send_subscription_status_email(subscription.pk, old_status)
                )
        event.processed_at = timezone.now()
        event.processing_error = ""
    except Exception as exc:
        event.processing_error = str(exc)[:2000]
        event.save(
            update_fields=("event_type", "payload", "occurred_at", "processing_error")
        )
        raise
    event.save(
        update_fields=(
            "event_type", "payload", "occurred_at", "processed_at", "processing_error"
        )
    )
    return event


def send_subscription_status_email(subscription_id, old_status=""):
    subscription = Subscription.objects.select_related("organization").get(pk=subscription_id)
    recipients = list(
        subscription.organization.memberships.filter(
            role="owner", is_active=True, user__is_active=True
        ).values_list("user__email", flat=True)
    )
    if not recipients:
        return
    try:
        send_mail(
            _("Estado de tu suscripción de Taller Pro"),
            _(
                "La suscripción de %(business)s cambió de %(old)s a %(new)s. "
                "Puedes revisar y administrar el plan en %(url)s."
            )
            % {
                "business": subscription.organization.name,
                "old": old_status or "-",
                "new": subscription.get_status_display(),
                "url": f"{settings.SITE_URL}/suscripcion/",
            },
            settings.DEFAULT_FROM_EMAIL,
            recipients,
        )
    except Exception:
        logger.exception(
            "Could not send billing status email", extra={"subscription_id": subscription_id}
        )
