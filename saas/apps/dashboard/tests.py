from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.billing.models import Subscription
from apps.organizations.models import Membership, Organization
from config.views import GOOGLE_SITE_VERIFICATION_CONTENT, GOOGLE_SITE_VERIFICATION_FILE


class DashboardTests(TestCase):
    def test_public_home_is_available_without_login(self):
        response = self.client.get(reverse("public-home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Probar el SaaS")
        self.assertContains(response, "+55 12 98112-3332")

    def test_public_home_can_switch_to_portuguese(self):
        response = self.client.get(reverse("public-home"), {"lang": "pt-br"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Testar o SaaS")
        self.assertContains(response, "Entrar no painel")
        self.assertEqual(response.cookies["django_language"].value, "pt-br")

    def test_dashboard_requires_login(self):
        response = self.client.get(reverse("dashboard"))
        self.assertRedirects(response, f"{reverse('login')}?next={reverse('dashboard')}")

    def test_dashboard_uses_users_organization(self):
        user = get_user_model().objects.create_user(
            email="owner@example.com", password="strong-password"
        )
        organization = Organization.objects.create(
            name="Taller Principal", slug="taller-principal"
        )
        Membership.objects.create(user=user, organization=organization)
        Subscription.objects.create(
            organization=organization,
            status=Subscription.Status.ACTIVE,
        )
        self.client.force_login(user)

        response = self.client.get(reverse("dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, organization.name)


class HealthCheckTests(TestCase):
    def test_health_check_reports_database_status(self):
        response = self.client.get(reverse("health-check"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})


class SiteVerificationTests(TestCase):
    def test_google_site_verification_file_is_served_at_root(self):
        response = self.client.get(f"/{GOOGLE_SITE_VERIFICATION_FILE}")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/plain")
        self.assertEqual(response.content.decode(), GOOGLE_SITE_VERIFICATION_CONTENT)
