from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.organizations.models import Membership, Organization

from .models import Subscription


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
