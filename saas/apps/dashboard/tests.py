import os
from unittest import skipUnless

from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import TestCase, override_settings
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

        privacy = self.client.get(reverse("legal-privacy"))
        self.assertContains(privacy, "Política de privacidade")
        self.assertContains(privacy, "Dados tratados")

    def test_dashboard_requires_login(self):
        response = self.client.get(reverse("dashboard"))
        self.assertRedirects(response, f"{reverse('login')}?next={reverse('dashboard')}")

    @override_settings(DEBUG=False)
    def test_custom_not_found_page_is_safe_and_actionable(self):
        response = self.client.get("/ruta-que-no-existe/")

        self.assertEqual(response.status_code, 404)
        self.assertContains(response, "Página no encontrada", status_code=404)
        self.assertContains(response, "Volver al inicio", status_code=404)

    @override_settings(PUBLIC_PLAN_PRICE_LABEL="US$ 19,99 por mes")
    def test_dashboard_uses_users_organization_and_exposes_main_tools(self):
        user = get_user_model().objects.create_user(
            email="owner@example.com", password="strong-password"
        )
        organization = Organization.objects.create(
            name="Taller Principal", slug="taller-principal"
        )
        Membership.objects.create(
            user=user,
            organization=organization,
            role=Membership.Role.OWNER,
        )
        Subscription.objects.create(
            organization=organization,
            status=Subscription.Status.ACTIVE,
        )
        self.client.force_login(user)

        response = self.client.get(reverse("dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, organization.name)
        self.assertContains(response, "Plan y pagos")
        self.assertContains(response, "US$ 19,99 por mes")
        self.assertContains(response, "Ver plan y formas de pago")
        self.assertContains(response, "Documentos y cobro")
        self.assertContains(response, reverse("billing-status"))


class HealthCheckTests(TestCase):
    def test_health_check_reports_database_status(self):
        response = self.client.get(reverse("health-check"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_liveness_does_not_depend_on_database_query(self):
        response = self.client.get(reverse("liveness-check"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "alive"})


class SiteVerificationTests(TestCase):
    def test_google_site_verification_file_is_served_at_root(self):
        response = self.client.get(f"/{GOOGLE_SITE_VERIFICATION_FILE}")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/plain")
        self.assertEqual(response.content.decode(), GOOGLE_SITE_VERIFICATION_CONTENT)


@skipUnless(os.environ.get("RUN_BROWSER_TESTS") == "true", "browser smoke is opt-in")
class BrowserSmokeTests(StaticLiveServerTestCase):
    """Critical browser journey executed by the dedicated CI browser job."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            email="browser@example.com", password="browser-password-2026"
        )
        organization = Organization.objects.create(
            name="Taller Browser", slug="taller-browser"
        )
        Membership.objects.create(
            user=self.user,
            organization=organization,
            role=Membership.Role.OWNER,
        )
        Subscription.objects.create(
            organization=organization, status=Subscription.Status.ACTIVE
        )

    def test_login_dashboard_and_primary_navigation(self):
        from playwright.sync_api import sync_playwright

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                page.goto(f"{self.live_server_url}{reverse('login')}")
                page.locator("#id_username").fill(self.user.email)
                page.locator("#id_password").fill("browser-password-2026")
                page.locator('button[type="submit"]').click()
                page.wait_for_url(f"**{reverse('dashboard')}")

                self.assertIn("Taller Browser", page.locator("body").inner_text())
                page.goto(f"{self.live_server_url}{reverse('customer-list')}")
                self.assertEqual(page.locator("h1").inner_text(), "Clientes")
                page.goto(f"{self.live_server_url}{reverse('quote-create')}")
                self.assertTrue(page.locator("#quote-items").is_visible())
                page.goto(f"{self.live_server_url}{reverse('billing-status')}")
                self.assertEqual(page.locator("h1").inner_text(), "Plan y pagos")
                self.assertIn(
                    "Formas de pago disponibles", page.locator("body").inner_text()
                )
                page.goto(f"{self.live_server_url}{reverse('organization-profile')}")
                self.assertIn("Documentos y cobro", page.locator("body").inner_text())
                self.assertTrue(page.locator("#id_default_payment_terms").is_visible())
            finally:
                browser.close()
