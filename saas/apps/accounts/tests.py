import re
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.billing.models import Subscription
from apps.organizations.models import Membership, Organization


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    SITE_URL="http://testserver",
)
class RegistrationTests(TestCase):
    def setUp(self):
        cache.clear()

    def registration_data(self, **overrides):
        data = {
            "first_name": "Ana",
            "last_name": "Silva",
            "email": "ana@example.com",
            "organization_name": "Taller Ana",
            "phone": "+55 12 99999-0000",
            "password1": "A-secure-password-2026",
            "password2": "A-secure-password-2026",
            "website": "",
        }
        data.update(overrides)
        return data

    def test_registration_creates_inactive_owner_and_trial(self):
        response = self.client.post(reverse("register"), self.registration_data())

        self.assertEqual(response.status_code, 200)
        user = get_user_model().objects.get(email="ana@example.com")
        membership = Membership.objects.get(user=user)
        subscription = Subscription.objects.get(organization=membership.organization)
        self.assertFalse(user.is_active)
        self.assertEqual(membership.role, Membership.Role.OWNER)
        self.assertEqual(subscription.status, Subscription.Status.TRIALING)
        self.assertIsNotNone(subscription.trial_ends_at)
        self.assertEqual(len(mail.outbox), 1)

    def test_activation_enables_and_logs_in_user(self):
        self.client.post(reverse("register"), self.registration_data())
        activation_path = re.search(
            r"http://testserver(/cuenta/activar/[^\s]+)", mail.outbox[0].body
        ).group(1)

        response = self.client.get(activation_path)

        user = get_user_model().objects.get(email="ana@example.com")
        self.assertTrue(user.is_active)
        self.assertRedirects(response, reverse("dashboard"))
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)

    def test_email_is_unique_case_insensitively(self):
        get_user_model().objects.create_user(
            email="ana@example.com", password="A-secure-password-2026"
        )

        response = self.client.post(
            reverse("register"),
            self.registration_data(email="ANA@EXAMPLE.COM"),
        )

        self.assertContains(response, "Ya existe una cuenta con este email")
        self.assertEqual(get_user_model().objects.count(), 1)

    def test_honeypot_rejects_automated_registration(self):
        response = self.client.post(
            reverse("register"), self.registration_data(website="https://spam.test")
        )

        self.assertContains(response, "Registro inválido")
        self.assertFalse(get_user_model().objects.exists())

    @patch("apps.accounts.views.send_activation_email", side_effect=RuntimeError("SMTP down"))
    def test_registration_survives_temporary_email_failure(self, mocked_send):
        response = self.client.post(reverse("register"), self.registration_data())

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No pudimos enviar el correo")
        self.assertTrue(get_user_model().objects.filter(email="ana@example.com").exists())
        mocked_send.assert_called_once()

    def test_resend_activation_does_not_reveal_unknown_email(self):
        response = self.client.post(
            reverse("resend-activation"), {"email": "unknown@example.com"}
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Si existe una cuenta pendiente")
        self.assertEqual(len(mail.outbox), 0)

    def test_password_reset_sends_email_for_active_user(self):
        get_user_model().objects.create_user(
            email="active@example.com", password="A-secure-password-2026"
        )

        response = self.client.post(
            reverse("password_reset"), {"email": "active@example.com"}
        )

        self.assertRedirects(response, reverse("password_reset_done"))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("/restablecer/", mail.outbox[0].body)

    def test_password_reset_supports_imported_user_without_usable_password(self):
        user = get_user_model().objects.create_user(
            email="imported@example.com", password=None
        )
        user.set_unusable_password()
        user.save(update_fields=("password",))

        response = self.client.post(
            reverse("password_reset"), {"email": "imported@example.com"}
        )

        self.assertRedirects(response, reverse("password_reset_done"))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("/restablecer/", mail.outbox[0].body)

    @override_settings(REGISTRATION_RATE_LIMIT=1)
    def test_registration_rate_limit_blocks_repeated_ip(self):
        first = self.client.post(
            reverse("register"),
            self.registration_data(email="first@example.com"),
            REMOTE_ADDR="203.0.113.10",
        )
        second = self.client.post(
            reverse("register"),
            self.registration_data(email="second@example.com"),
            REMOTE_ADDR="203.0.113.10",
        )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 429)
        self.assertContains(
            second,
            "Demasiados intentos de registro",
            status_code=429,
        )
        self.assertFalse(
            get_user_model().objects.filter(email="second@example.com").exists()
        )
