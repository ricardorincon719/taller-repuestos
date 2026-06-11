from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase

from .models import Membership, Organization


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
