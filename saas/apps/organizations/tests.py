from django.contrib.auth import get_user_model
from django.core import mail
from django.db import IntegrityError, transaction
from django.urls import reverse
from django.test import TestCase, override_settings

from apps.customers.models import Customer
from apps.billing.models import Subscription

from .models import Membership, Organization, OrganizationDeletionRequest


class MembershipTests(TestCase):
    def test_user_cannot_have_duplicate_membership_in_same_organization(self):
        user = get_user_model().objects.create_user(email="owner@example.com")
        organization = Organization.objects.create(name="Taller Uno", slug="taller-uno")
        Membership.objects.create(
            user=user,
            organization=organization,
            role=Membership.Role.OWNER,
        )

        with self.assertRaises(IntegrityError), transaction.atomic():
            Membership.objects.create(user=user, organization=organization)


class OrganizationProfileTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            email="owner@example.com", password="secret123"
        )
        self.organization = Organization.objects.create(
            name="Taller Uno", slug="taller-uno"
        )
        Membership.objects.create(
            user=self.user,
            organization=self.organization,
            role=Membership.Role.OWNER,
        )
        self.client.force_login(self.user)

    def test_profile_updates_business_type_and_language(self):
        response = self.client.post(
            reverse("organization-profile"),
            {
                "name": "Oficina Central",
                "business_type": Organization.BusinessType.OFFICE,
                "language": Organization.Language.PORTUGUESE_BR,
                "email": "contato@example.com",
                "phone": "+55 11 99999-0000",
                "address": "Rua Central 123",
                "legal_name": "Oficina Central Ltda.",
                "city": "São Paulo",
                "country": Organization.Country.BRAZIL,
                "currency": Organization.Currency.BRL,
                "timezone": "America/Sao_Paulo",
                "tax_id": "12.345.678/0001-90",
                "quote_prefix": "ORC",
                "default_quote_terms": "Válido por 15 dias.",
                "default_warranty_text": "Garantia de 90 dias.",
                "default_payment_terms": "Pagamento na entrega.",
                "default_footer": "Obrigado pela preferência.",
                "public_quote_valid_days": 90,
            },
            follow=True,
        )

        self.organization.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.organization.business_type, Organization.BusinessType.OFFICE)
        self.assertEqual(self.organization.language, Organization.Language.PORTUGUESE_BR)
        self.assertContains(response, "Perfil do negócio")
        self.assertContains(response, "Idioma do sistema")

    def test_regular_member_cannot_edit_business_profile(self):
        self.organization.memberships.filter(user=self.user).update(
            role=Membership.Role.MEMBER
        )

        response = self.client.get(reverse("organization-profile"))

        self.assertEqual(response.status_code, 403)


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    SITE_URL="http://testserver",
)
class OrganizationTeamTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(
            email="owner-team@example.com", password="secret123"
        )
        self.organization = Organization.objects.create(
            name="Taller Equipo", slug="taller-equipo"
        )
        Membership.objects.create(
            user=self.owner,
            organization=self.organization,
            role=Membership.Role.OWNER,
        )
        self.client.force_login(self.owner)

    def test_owner_can_invite_a_member(self):
        response = self.client.post(
            reverse("organization-team"),
            {"email": "member@example.com", "role": Membership.Role.MEMBER},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        invitation = self.organization.invitations.get(email="member@example.com")
        self.assertTrue(invitation.is_valid)
        self.assertEqual(len(mail.outbox), 1)

        revoke = self.client.post(
            reverse("organization-invitation-revoke", args=(invitation.pk,))
        )
        invitation.refresh_from_db()
        self.assertRedirects(revoke, reverse("organization-team"))
        self.assertIsNotNone(invitation.revoked_at)

    def test_sole_owner_cannot_be_demoted(self):
        membership = self.organization.memberships.get(user=self.owner)

        response = self.client.post(
            reverse("organization-member-update", args=(membership.pk,)),
            {"role": Membership.Role.ADMIN, "is_active": "on"},
        )

        self.assertEqual(response.status_code, 403)
        membership.refresh_from_db()
        self.assertEqual(membership.role, Membership.Role.OWNER)


class OrganizationExportTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(
            email="export@example.com", password="secret123"
        )
        self.organization = Organization.objects.create(
            name="Taller Export", slug="taller-export"
        )
        Membership.objects.create(
            user=self.owner,
            organization=self.organization,
            role=Membership.Role.OWNER,
        )
        Customer.objects.create(organization=self.organization, name="Cliente Propio")
        other = Organization.objects.create(name="Otro Taller", slug="otro-taller")
        Customer.objects.create(organization=other, name="Cliente Ajeno")
        self.client.force_login(self.owner)

    def test_export_contains_only_current_organization(self):
        response = self.client.get(reverse("organization-export"))

        self.assertEqual(response.status_code, 200)
        self.assertIn("attachment", response["Content-Disposition"])
        customer_names = {item["name"] for item in response.json()["customers"]}
        self.assertEqual(customer_names, {"Cliente Propio"})

    def test_deletion_requires_external_subscription_cancellation(self):
        subscription = Subscription.objects.create(
            organization=self.organization,
            status=Subscription.Status.ACTIVE,
            provider_customer_id="ctm_delete",
            provider_subscription_id="sub_delete",
        )
        payload = {
            "organization_name": self.organization.name,
            "password": "secret123",
        }

        blocked = self.client.post(reverse("organization-delete"), payload)

        self.assertEqual(blocked.status_code, 200)
        self.assertContains(blocked, "Cancela primero la renovación")
        self.assertFalse(OrganizationDeletionRequest.objects.exists())

        subscription.cancel_at_period_end = True
        subscription.save(update_fields=("cancel_at_period_end",))
        allowed = self.client.post(reverse("organization-delete"), payload)

        self.assertRedirects(allowed, reverse("organization-delete"))
        self.assertTrue(OrganizationDeletionRequest.objects.exists())


import json
from decimal import Decimal
from io import StringIO
from tempfile import TemporaryDirectory
from pathlib import Path

from django.core import mail
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings

from apps.billing.models import Subscription
from apps.customers.models import Customer
from apps.quotes.models import Quote


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    SITE_URL="http://testserver",
)
class StreamlitImportCommandTests(TestCase):
    def setUp(self):
        self.temp_dir = TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.users_file = Path(self.temp_dir.name) / "usuarios.json"
        self.quotes_file = Path(self.temp_dir.name) / "presupuestos.json"
        self.users = {
            "legacy@example.com": {
                "email": "legacy@example.com",
                "password": "$2b$12$legacyhashmustnotbecopied",
                "fecha_registro": "2026-01-10",
                "estado": "activo",
                "plan": "profesional",
            }
        }
        self.quotes = [
            {
                "id": 1,
                "fecha": "2026-01-11 10:30",
                "cliente": "Cliente Uno",
                "telefono": "123",
                "email": "cliente@example.com",
                "repuestos": 50,
                "mano_obra": 100,
                "items": [{"nombre": "Filtro", "precio": 25}],
                "total": 175,
                "notas": "Nota",
                "estado": "FACTURADO",
                "usuario_creador": "legacy@example.com",
            },
            {
                "id": 2,
                "fecha": "2026-01-12 11:00",
                "cliente": "Cliente Uno",
                "telefono": "123",
                "email": "cliente@example.com",
                "repuestos": 0,
                "mano_obra": 80,
                "items": [],
                "total": 80,
                "notas": "",
                "estado": "RECHAZADO",
                "usuario_creador": "legacy@example.com",
            },
        ]
        self._write_sources()

    def _write_sources(self):
        self.users_file.write_text(json.dumps(self.users), encoding="utf-8")
        self.quotes_file.write_text(json.dumps(self.quotes), encoding="utf-8")

    def run_import(self, **options):
        output = StringIO()
        call_command(
            "import_streamlit_data",
            users_file=self.users_file,
            quotes_file=self.quotes_file,
            stdout=output,
            **options,
        )
        return output.getvalue()

    def test_dry_run_rolls_back_all_changes(self):
        output = self.run_import(dry_run=True)

        self.assertIn("SIMULACIÓN COMPLETADA", output)
        self.assertFalse(get_user_model().objects.exists())
        self.assertFalse(Organization.objects.exists())
        self.assertFalse(Quote.objects.exists())

    def test_import_preserves_totals_status_and_is_idempotent(self):
        self.run_import()

        user = get_user_model().objects.get(email="legacy@example.com")
        organization = Organization.objects.get()
        subscription = Subscription.objects.get(organization=organization)
        first_quote = Quote.objects.get(legacy_id="1")
        self.assertTrue(user.is_active)
        self.assertFalse(user.has_usable_password())
        self.assertEqual(subscription.status, Subscription.Status.ACTIVE)
        self.assertEqual(Customer.objects.count(), 1)
        self.assertEqual(Quote.objects.count(), 2)
        self.assertEqual(first_quote.status, Quote.Status.INVOICED)
        self.assertEqual(first_quote.total_amount, Decimal("175.00"))
        self.assertEqual(first_quote.items.count(), 2)
        self.assertEqual(organization.next_quote_number, 3)

        output = self.run_import()

        self.assertIn("quotes_skipped: 2", output)
        self.assertEqual(get_user_model().objects.count(), 1)
        self.assertEqual(Customer.objects.count(), 1)
        self.assertEqual(Quote.objects.count(), 2)

    def test_send_invitations_can_run_after_initial_import(self):
        self.run_import()
        self.run_import(send_invitations=True)

        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("/restablecer/", mail.outbox[0].body)

    def test_invalid_owner_rolls_back_import(self):
        self.quotes[0]["usuario_creador"] = "unknown@example.com"
        self._write_sources()

        with self.assertRaises(CommandError):
            self.run_import()

        self.assertFalse(get_user_model().objects.exists())
        self.assertFalse(Organization.objects.exists())
