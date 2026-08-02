import hashlib
import hmac
import json
import time
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.organizations.models import Membership, Organization

from .models import Subscription, WebhookEvent
from .services import process_paddle_webhook, verify_paddle_signature


class SubscriptionAccessTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(
            name="Taller Uno", slug="billing-taller-uno"
        )

    def test_active_subscription_allows_access(self):
        subscription = Subscription.objects.create(
            organization=self.organization,
            status=Subscription.Status.ACTIVE,
        )

        self.assertTrue(subscription.allows_access)

    def test_trial_access_depends_on_expiration(self):
        subscription = Subscription.objects.create(
            organization=self.organization,
            status=Subscription.Status.TRIALING,
            trial_ends_at=timezone.now() + timedelta(hours=1),
        )
        self.assertTrue(subscription.allows_access)

        subscription.trial_ends_at = timezone.now() - timedelta(seconds=1)
        self.assertFalse(subscription.allows_access)


class BillingViewsTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            email="expired@example.com", password="strong-password"
        )
        self.organization = Organization.objects.create(
            name="Taller Vencido", slug="taller-vencido"
        )
        Membership.objects.create(user=self.user, organization=self.organization)
        Subscription.objects.create(
            organization=self.organization,
            status=Subscription.Status.TRIALING,
            trial_ends_at=timezone.now() - timedelta(days=1),
        )
        self.client.force_login(self.user)

    def test_expired_trial_redirects_dashboard_to_billing(self):
        response = self.client.get(reverse("dashboard"))

        self.assertRedirects(response, reverse("billing-status"))

    def test_billing_status_remains_accessible(self):
        response = self.client.get(reverse("billing-status"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "El acceso está pausado")


@override_settings(
    PADDLE_WEBHOOK_SECRET="webhook-test-secret",
    PADDLE_PROFESSIONAL_PRICE_ID="pri_professional",
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
)
class PaddleWebhookTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(
            name="Taller Paddle", slug="taller-paddle"
        )
        self.subscription = Subscription.objects.create(
            organization=self.organization,
            status=Subscription.Status.TRIALING,
        )

    def payload(self, *, event_id="evt_1", status="active", occurred_at=None):
        occurred_at = occurred_at or timezone.now()
        return {
            "event_id": event_id,
            "event_type": "subscription.updated",
            "occurred_at": occurred_at.isoformat(),
            "data": {
                "id": "sub_1",
                "customer_id": "ctm_1",
                "status": status,
                "custom_data": {"organization_id": str(self.organization.pk)},
                "items": [{"price": {"id": "pri_professional"}}],
                "current_billing_period": {
                    "ends_at": (timezone.now() + timedelta(days=30)).isoformat()
                },
            },
        }

    def test_signature_matches_raw_request_body(self):
        body = json.dumps(self.payload()).encode()
        timestamp = int(time.time())
        digest = hmac.new(
            b"webhook-test-secret",
            str(timestamp).encode() + b":" + body,
            hashlib.sha256,
        ).hexdigest()

        self.assertIsNone(
            verify_paddle_signature(body, f"ts={timestamp};h1={digest}")
        )

    def test_processing_is_idempotent_and_maps_subscription(self):
        body = json.dumps(self.payload()).encode()

        first = process_paddle_webhook(body)
        second = process_paddle_webhook(body)

        self.subscription.refresh_from_db()
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(WebhookEvent.objects.count(), 1)
        self.assertEqual(self.subscription.status, Subscription.Status.ACTIVE)
        self.assertEqual(self.subscription.plan, Subscription.Plan.PROFESSIONAL)
        self.assertEqual(self.subscription.provider_subscription_id, "sub_1")

    def test_older_event_cannot_roll_subscription_back(self):
        newest = timezone.now()
        process_paddle_webhook(
            json.dumps(self.payload(event_id="evt_new", occurred_at=newest)).encode()
        )
        process_paddle_webhook(
            json.dumps(
                self.payload(
                    event_id="evt_old",
                    status="canceled",
                    occurred_at=newest - timedelta(hours=1),
                )
            ).encode()
        )

        self.subscription.refresh_from_db()
        self.assertEqual(self.subscription.status, Subscription.Status.ACTIVE)


class BillingPortalTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(
            email="portal@example.com", password="strong-password"
        )
        organization = Organization.objects.create(
            name="Taller Portal", slug="taller-portal"
        )
        Membership.objects.create(
            user=self.owner,
            organization=organization,
            role=Membership.Role.OWNER,
        )
        Subscription.objects.create(
            organization=organization,
            status=Subscription.Status.ACTIVE,
            provider_customer_id="ctm_portal",
            provider_subscription_id="sub_portal",
        )
        self.client.force_login(self.owner)

    @patch(
        "apps.billing.views.create_customer_portal_session",
        return_value="https://customer-portal.paddle.com/session",
    )
    def test_owner_can_open_customer_portal(self, mocked_portal):
        response = self.client.post(reverse("billing-portal"))

        self.assertRedirects(
            response,
            "https://customer-portal.paddle.com/session",
            fetch_redirect_response=False,
        )
        mocked_portal.assert_called_once()

    @override_settings(
        PADDLE_ENABLED=True,
        PADDLE_ENVIRONMENT="sandbox",
        PADDLE_CLIENT_TOKEN="test_client_token",
        PADDLE_PROFESSIONAL_PRICE_ID="pri_test",
        PUBLIC_PLAN_PRICE_LABEL="US$ 19,99 por mes",
    )
    def test_owner_can_subscribe_during_trial(self):
        subscription = self.owner.organization_memberships.get().organization.subscription
        subscription.status = Subscription.Status.TRIALING
        subscription.provider_customer_id = ""
        subscription.provider_subscription_id = ""
        subscription.trial_ends_at = timezone.now() + timedelta(days=7)
        subscription.save()

        response = self.client.get(reverse("billing-status"))

        self.assertContains(response, "Contratar Taller Pro")
        self.assertContains(response, "Formas de pago disponibles")
        self.assertContains(response, "US$ 19,99 por mes")
        self.assertContains(response, "Paddle.PricePreview")
        self.assertContains(response, "pri_test")

    @override_settings(
        PADDLE_ENABLED=True,
        PADDLE_ENVIRONMENT="sandbox",
        PADDLE_CLIENT_TOKEN="test_client_token",
        PADDLE_PROFESSIONAL_PRICE_ID="pri_test",
    )
    def test_member_can_review_payment_options_but_not_manage_billing(self):
        organization = self.owner.organization_memberships.get().organization
        member = get_user_model().objects.create_user(
            email="member-billing@example.com", password="strong-password"
        )
        Membership.objects.create(
            user=member,
            organization=organization,
            role=Membership.Role.MEMBER,
        )
        self.client.force_login(member)

        response = self.client.get(reverse("billing-status"))

        self.assertContains(response, "Formas de pago disponibles")
        self.assertContains(response, "Solo el propietario del negocio puede contratar")
        self.assertContains(response, "Paddle.PricePreview")
        self.assertNotContains(response, 'id="paddle-checkout"')
        self.assertNotContains(response, f'action="{reverse("billing-portal")}"')
