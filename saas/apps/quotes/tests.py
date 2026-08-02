from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from apps.billing.models import Subscription
from apps.customers.models import Customer, Vehicle
from apps.organizations.models import Membership, Organization

from .models import Quote, QuoteItem
from .services import build_quote_pdf, change_quote_status, create_quote


class QuoteServiceTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            email="owner@example.com", password="strong-password"
        )
        self.organization = Organization.objects.create(
            name="Taller Uno", slug="taller-uno"
        )
        Membership.objects.create(
            user=self.user,
            organization=self.organization,
            role=Membership.Role.OWNER,
        )
        Subscription.objects.create(
            organization=self.organization,
            status=Subscription.Status.ACTIVE,
        )
        self.customer = Customer.objects.create(
            organization=self.organization,
            name="Cliente Uno",
        )

    def test_quote_numbers_increment_per_organization(self):
        first = create_quote(
            organization=self.organization,
            customer=self.customer,
            created_by=self.user,
        )
        second = create_quote(
            organization=self.organization,
            customer=self.customer,
            created_by=self.user,
        )

        self.assertEqual(first.number, 1)
        self.assertEqual(second.number, 2)
        self.organization.refresh_from_db()
        self.assertEqual(self.organization.next_quote_number, 3)

    def test_quote_rejects_customer_from_another_organization(self):
        other = Organization.objects.create(name="Taller Dos", slug="taller-dos")
        outsider = Customer.objects.create(organization=other, name="Cliente Ajeno")
        quote = Quote(
            organization=self.organization,
            number=1,
            customer=outsider,
            created_by=self.user,
        )

        with self.assertRaises(ValidationError):
            quote.full_clean()

    def test_totals_use_decimal_values(self):
        quote = create_quote(
            organization=self.organization,
            customer=self.customer,
            created_by=self.user,
            labor_amount=Decimal("100.50"),
            discount_amount=Decimal("10.00"),
        )
        QuoteItem.objects.create(
            quote=quote,
            description="Filtro",
            quantity=Decimal("2.00"),
            unit_price=Decimal("25.25"),
        )

        quote.refresh_from_db()
        self.assertEqual(quote.items_amount, Decimal("50.50"))
        self.assertEqual(quote.total_amount, Decimal("141.00"))

    def test_quote_detail_is_isolated_by_organization(self):
        other_user = get_user_model().objects.create_user(
            email="other@example.com", password="strong-password"
        )
        other = Organization.objects.create(name="Taller Dos", slug="taller-dos")
        Membership.objects.create(user=other_user, organization=other)
        outsider = Customer.objects.create(organization=other, name="Cliente Ajeno")
        outsider_quote = create_quote(
            organization=other,
            customer=outsider,
            created_by=other_user,
        )

        self.client.force_login(self.user)
        response = self.client.get(reverse("quote-detail", args=(outsider_quote.pk,)))

        self.assertEqual(response.status_code, 404)


    def test_quote_create_view_persists_multiple_items_and_totals(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("quote-create"),
            {
                "customer": self.customer.pk,
                "vehicle": "",
                "status": Quote.Status.DRAFT,
                "labor_amount": "100.00",
                "discount_amount": "5.00",
                "valid_until": "",
                "notes": "Cambio de aceite",
                "items-TOTAL_FORMS": "2",
                "items-INITIAL_FORMS": "0",
                "items-MIN_NUM_FORMS": "0",
                "items-MAX_NUM_FORMS": "1000",
                "items-0-description": "Filtro",
                "items-0-quantity": "2.00",
                "items-0-unit_price": "25.00",
                "items-1-description": "Aceite",
                "items-1-quantity": "1.00",
                "items-1-unit_price": "40.00",
            },
        )

        quote = Quote.objects.get(organization=self.organization)
        self.assertRedirects(response, reverse("quote-detail", args=(quote.pk,)))
        self.assertEqual(quote.items.count(), 2)
        self.assertEqual(quote.items_amount, Decimal("90.00"))
        self.assertEqual(quote.total_amount, Decimal("185.00"))

    def test_quote_create_view_exposes_dynamic_item_controls(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("quote-create"))

        self.assertContains(response, "Agregar ítem")
        self.assertContains(response, "quote-item-template")
        self.assertContains(response, "Total estimado")

    def test_quote_form_only_lists_current_organization_data(self):
        other = Organization.objects.create(name="Taller Dos", slug="taller-dos")
        outsider = Customer.objects.create(organization=other, name="Cliente Ajeno")
        Vehicle.objects.create(
            organization=other,
            customer=outsider,
            license_plate="XYZ1234",
        )

        self.client.force_login(self.user)
        response = self.client.get(reverse("quote-create"))

        self.assertContains(response, self.customer.name)
        self.assertNotContains(response, outsider.name)
        self.assertNotContains(response, "XYZ1234")

    def test_quote_status_update_is_post_only(self):
        quote = create_quote(
            organization=self.organization,
            customer=self.customer,
            created_by=self.user,
        )
        self.client.force_login(self.user)

        get_response = self.client.get(reverse("quote-status-update", args=(quote.pk,)))
        self.assertEqual(get_response.status_code, 405)

        sent_response = self.client.post(
            reverse("quote-status-update", args=(quote.pk,)),
            {"status": Quote.Status.SENT},
        )
        self.assertRedirects(sent_response, reverse("quote-detail", args=(quote.pk,)))
        response = self.client.post(
            reverse("quote-status-update", args=(quote.pk,)),
            {"status": Quote.Status.APPROVED},
        )
        quote.refresh_from_db()
        self.assertRedirects(response, reverse("quote-detail", args=(quote.pk,)))
        self.assertEqual(quote.status, Quote.Status.APPROVED)

    def test_issued_quote_is_immutable_and_can_be_duplicated(self):
        quote = create_quote(
            organization=self.organization,
            customer=self.customer,
            created_by=self.user,
        )
        QuoteItem.objects.create(
            quote=quote, description="Filtro", quantity=1, unit_price=25
        )
        self.client.force_login(self.user)
        self.client.post(
            reverse("quote-status-update", args=(quote.pk,)),
            {"status": Quote.Status.SENT},
        )
        quote.refresh_from_db()
        self.assertTrue(quote.issue_snapshot)

        edit_response = self.client.get(reverse("quote-update", args=(quote.pk,)))
        self.assertRedirects(edit_response, reverse("quote-detail", args=(quote.pk,)))

        duplicate_response = self.client.post(
            reverse("quote-duplicate", args=(quote.pk,))
        )
        copy = Quote.objects.exclude(pk=quote.pk).get(source_quote=quote)
        self.assertRedirects(
            duplicate_response, reverse("quote-update", args=(copy.pk,))
        )
        self.assertEqual(copy.status, Quote.Status.DRAFT)
        self.assertEqual(copy.items.count(), 1)

    def test_draft_edit_can_remove_item_and_recalculate_totals(self):
        quote = create_quote(
            organization=self.organization,
            customer=self.customer,
            created_by=self.user,
            labor_amount=Decimal("100.00"),
        )
        item = QuoteItem.objects.create(
            quote=quote,
            description="Filtro viejo",
            quantity=Decimal("1.00"),
            unit_price=Decimal("25.00"),
        )
        quote.recalculate_totals()
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("quote-update", args=(quote.pk,)),
            {
                "customer": self.customer.pk,
                "vehicle": "",
                "labor_amount": "80.00",
                "discount_amount": "0.00",
                "valid_until": "",
                "notes": "Actualizado",
                "items-TOTAL_FORMS": "1",
                "items-INITIAL_FORMS": "1",
                "items-MIN_NUM_FORMS": "0",
                "items-MAX_NUM_FORMS": "1000",
                "items-0-id": item.pk,
                "items-0-description": item.description,
                "items-0-quantity": "1.00",
                "items-0-unit_price": "25.00",
                "items-0-DELETE": "on",
            },
        )

        quote.refresh_from_db()
        self.assertRedirects(response, reverse("quote-detail", args=(quote.pk,)))
        self.assertEqual(quote.items.count(), 0)
        self.assertEqual(quote.total_amount, Decimal("80.00"))

    def test_issued_snapshot_preserves_customer_and_business_identity(self):
        quote = create_quote(
            organization=self.organization,
            customer=self.customer,
            created_by=self.user,
        )
        change_quote_status(quote=quote, new_status=Quote.Status.SENT, actor=self.user)
        self.organization.name = "Nombre Nuevo"
        self.organization.save(update_fields=("name",))
        self.customer.name = "Cliente Nuevo"
        self.customer.save(update_fields=("name",))

        response = self.client.get(
            reverse("public-quote-detail", args=(quote.share_token,))
        )

        self.assertContains(response, "Taller Uno")
        self.assertContains(response, "Cliente Uno")
        self.assertNotContains(response, "Nombre Nuevo")
        self.assertNotContains(response, "Cliente Nuevo")

    def test_public_customer_can_approve_sent_quote_once(self):
        quote = create_quote(
            organization=self.organization,
            customer=self.customer,
            created_by=self.user,
        )
        self.client.force_login(self.user)
        self.client.post(
            reverse("quote-status-update", args=(quote.pk,)),
            {"status": Quote.Status.SENT},
        )
        self.client.logout()

        response = self.client.post(
            reverse("public-quote-decision", args=(quote.share_token,)),
            {"decision": "approve"},
            REMOTE_ADDR="203.0.113.22",
        )

        quote.refresh_from_db()
        self.assertRedirects(
            response, reverse("public-quote-detail", args=(quote.share_token,))
        )
        self.assertEqual(quote.status, Quote.Status.APPROVED)
        self.assertEqual(
            quote.events.filter(
                event_type="quote.status_changed", to_status=Quote.Status.APPROVED
            ).count(),
            1,
        )

    def test_revoked_public_link_returns_not_found(self):
        quote = create_quote(
            organization=self.organization,
            customer=self.customer,
            created_by=self.user,
        )
        change_quote_status(quote=quote, new_status=Quote.Status.SENT, actor=self.user)
        self.client.force_login(self.user)

        self.client.post(
            reverse("quote-share-update", args=(quote.pk,)), {"action": "revoke"}
        )
        self.client.logout()

        response = self.client.get(
            reverse("public-quote-detail", args=(quote.share_token,))
        )
        self.assertEqual(response.status_code, 404)

    def test_draft_is_not_public_and_cannot_generate_link(self):
        quote = create_quote(
            organization=self.organization,
            customer=self.customer,
            created_by=self.user,
        )

        public_response = self.client.get(
            reverse("public-quote-detail", args=(quote.share_token,))
        )
        self.client.force_login(self.user)
        renew_response = self.client.post(
            reverse("quote-share-update", args=(quote.pk,)), {"action": "renew"}
        )

        self.assertEqual(public_response.status_code, 404)
        self.assertEqual(renew_response.status_code, 400)

    def test_public_quote_and_pdf_use_share_token(self):
        quote = create_quote(
            organization=self.organization,
            customer=self.customer,
            created_by=self.user,
        )
        QuoteItem.objects.create(
            quote=quote,
            description="Filtro",
            quantity=Decimal("1.00"),
            unit_price=Decimal("25.00"),
        )
        change_quote_status(quote=quote, new_status=Quote.Status.SENT, actor=self.user)

        public_response = self.client.get(
            reverse("public-quote-detail", args=(quote.share_token,))
        )
        pdf_response = self.client.get(
            reverse("public-quote-pdf", args=(quote.share_token,))
        )

        self.assertEqual(public_response.status_code, 200)
        self.assertContains(public_response, quote.display_number)
        self.assertEqual(pdf_response.status_code, 200)
        self.assertEqual(pdf_response["Content-Type"], "application/pdf")
        self.assertTrue(pdf_response.content.startswith(b"%PDF"))

    def test_public_quote_uses_organization_language_and_profile_data(self):
        self.organization.language = Organization.Language.PORTUGUESE_BR
        self.organization.business_type = Organization.BusinessType.OFFICE
        self.organization.email = "contato@example.com"
        self.organization.phone = "+55 11 99999-0000"
        self.organization.tax_id = "12.345.678/0001-90"
        self.organization.address = "Rua Central 123"
        self.organization.save()
        quote = create_quote(
            organization=self.organization,
            customer=self.customer,
            created_by=self.user,
            labor_amount=Decimal("100.00"),
        )
        change_quote_status(quote=quote, new_status=Quote.Status.SENT, actor=self.user)

        response = self.client.get(
            reverse("public-quote-detail", args=(quote.share_token,))
        )

        self.assertContains(response, "Baixar PDF")
        self.assertContains(response, "Detalhe")
        self.assertContains(response, "Escritório administrativo")
        self.assertContains(response, "contato@example.com")
        self.assertContains(response, "12.345.678/0001-90")
        self.assertContains(response, "Rua Central 123")

    def test_pdf_builds_with_organization_profile_data(self):
        self.organization.language = Organization.Language.PORTUGUESE_BR
        self.organization.business_type = Organization.BusinessType.OFFICE
        self.organization.email = "contato@example.com"
        self.organization.phone = "+55 11 99999-0000"
        self.organization.tax_id = "12.345.678/0001-90"
        self.organization.address = "Rua Central 123"
        self.organization.save()
        quote = create_quote(
            organization=self.organization,
            customer=self.customer,
            created_by=self.user,
            labor_amount=Decimal("100.00"),
        )

        content = build_quote_pdf(quote)

        self.assertTrue(content.startswith(b"%PDF"))
        self.assertGreater(len(content), 1000)

    def test_authenticated_pdf_is_isolated_by_organization(self):
        other_user = get_user_model().objects.create_user(
            email="other-pdf@example.com", password="strong-password"
        )
        other = Organization.objects.create(name="Taller Dos", slug="taller-dos-pdf")
        Membership.objects.create(user=other_user, organization=other)
        outsider = Customer.objects.create(organization=other, name="Cliente Ajeno")
        outsider_quote = create_quote(
            organization=other,
            customer=outsider,
            created_by=other_user,
        )
        self.client.force_login(self.user)

        response = self.client.get(reverse("quote-pdf", args=(outsider_quote.pk,)))

        self.assertEqual(response.status_code, 404)
