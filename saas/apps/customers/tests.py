from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from apps.billing.models import Subscription
from apps.organizations.models import Membership, Organization

from .models import Customer, Vehicle


class VehicleIsolationTests(TestCase):
    def test_vehicle_rejects_customer_from_another_organization(self):
        first = Organization.objects.create(name="Taller Uno", slug="taller-uno")
        second = Organization.objects.create(name="Taller Dos", slug="taller-dos")
        outsider = Customer.objects.create(organization=second, name="Cliente Ajeno")
        vehicle = Vehicle(
            organization=first,
            customer=outsider,
            license_plate="ABC1234",
        )

        with self.assertRaises(ValidationError):
            vehicle.full_clean()


class CustomerViewsTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            email="owner@example.com", password="strong-password"
        )
        self.organization = Organization.objects.create(
            name="Taller Uno", slug="taller-uno"
        )
        Membership.objects.create(user=self.user, organization=self.organization)
        Subscription.objects.create(
            organization=self.organization,
            status=Subscription.Status.ACTIVE,
        )
        self.client.force_login(self.user)

    def test_customer_create_assigns_current_organization(self):
        response = self.client.post(
            reverse("customer-create"),
            {
                "name": "Cliente Uno",
                "phone": "123",
                "email": "cliente@example.com",
                "tax_id": "",
                "address": "",
                "notes": "",
            },
        )

        customer = Customer.objects.get(name="Cliente Uno")
        self.assertEqual(customer.organization, self.organization)
        self.assertRedirects(response, reverse("customer-detail", args=(customer.pk,)))

    def test_customer_detail_from_other_organization_returns_404(self):
        other = Organization.objects.create(name="Taller Dos", slug="taller-dos")
        outsider = Customer.objects.create(organization=other, name="Cliente Ajeno")

        response = self.client.get(reverse("customer-detail", args=(outsider.pk,)))

        self.assertEqual(response.status_code, 404)

    def test_vehicle_cannot_be_created_for_outsider_customer(self):
        other = Organization.objects.create(name="Taller Dos", slug="taller-dos")
        outsider = Customer.objects.create(organization=other, name="Cliente Ajeno")

        response = self.client.post(
            reverse("vehicle-create", args=(outsider.pk,)),
            {"license_plate": "ABC1234", "make": "Fiat", "model": "Uno", "year": 2020, "notes": ""},
        )

        self.assertEqual(response.status_code, 404)
        self.assertFalse(Vehicle.objects.exists())

    def test_archive_customer_is_post_only_and_reversible(self):
        customer = Customer.objects.create(
            organization=self.organization, name="Cliente Uno"
        )

        get_response = self.client.get(reverse("customer-archive", args=(customer.pk,)))
        self.assertEqual(get_response.status_code, 405)

        self.client.post(reverse("customer-archive", args=(customer.pk,)))
        customer.refresh_from_db()
        self.assertFalse(customer.is_active)

        self.client.post(reverse("customer-archive", args=(customer.pk,)))
        customer.refresh_from_db()
        self.assertTrue(customer.is_active)

    def test_vehicle_plate_is_normalized(self):
        customer = Customer.objects.create(
            organization=self.organization, name="Cliente Uno"
        )

        self.client.post(
            reverse("vehicle-create", args=(customer.pk,)),
            {"license_plate": "abc1234", "make": "Fiat", "model": "Uno", "year": 2020, "notes": ""},
        )

        self.assertEqual(Vehicle.objects.get().license_plate, "ABC1234")

    def test_duplicate_vehicle_plate_returns_form_error(self):
        customer = Customer.objects.create(
            organization=self.organization, name="Cliente Uno"
        )
        Vehicle.objects.create(
            organization=self.organization,
            customer=customer,
            license_plate="ABC1234",
        )

        response = self.client.post(
            reverse("vehicle-create", args=(customer.pk,)),
            {
                "license_plate": "abc1234",
                "make": "Fiat",
                "model": "Uno",
                "year": 2020,
                "notes": "",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Ya existe un vehículo con esta matrícula")
        self.assertEqual(Vehicle.objects.count(), 1)

    def test_archived_customer_cannot_receive_new_vehicle(self):
        customer = Customer.objects.create(
            organization=self.organization,
            name="Cliente Uno",
            is_active=False,
        )

        response = self.client.post(
            reverse("vehicle-create", args=(customer.pk,)),
            {
                "license_plate": "ABC1234",
                "make": "Fiat",
                "model": "Uno",
                "year": 2020,
                "notes": "",
            },
        )

        self.assertEqual(response.status_code, 404)
        self.assertFalse(Vehicle.objects.exists())
