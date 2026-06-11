from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.billing.decorators import subscription_required
from apps.organizations.services import get_current_membership

from .forms import CustomerForm, VehicleForm
from .models import Customer, Vehicle


def current_organization(request):
    return get_current_membership(request.user).organization


@login_required
@subscription_required
def customer_list(request):
    organization = current_organization(request)
    show_archived = request.GET.get("archivados") == "1"
    query = request.GET.get("q", "").strip()
    customers = Customer.objects.for_organization(organization).filter(
        is_active=not show_archived
    ).annotate(
        vehicle_count=Count("vehicles", filter=Q(vehicles__is_active=True))
    )
    if query:
        customers = customers.filter(
            Q(name__icontains=query)
            | Q(phone__icontains=query)
            | Q(email__icontains=query)
            | Q(tax_id__icontains=query)
        )
    return render(
        request,
        "customers/list.html",
        {
            "organization": organization,
            "customers": customers,
            "query": query,
            "show_archived": show_archived,
        },
    )


@login_required
@subscription_required
def customer_detail(request, pk):
    organization = current_organization(request)
    customer = get_object_or_404(
        Customer.objects.for_organization(organization).prefetch_related("vehicles"),
        pk=pk,
    )
    quotes = customer.quotes.filter(organization=organization).select_related("vehicle")[:10]
    return render(
        request,
        "customers/detail.html",
        {"organization": organization, "customer": customer, "quotes": quotes},
    )


@login_required
@subscription_required
def customer_create(request):
    organization = current_organization(request)
    form = CustomerForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        customer = form.save(commit=False)
        customer.organization = organization
        customer.full_clean()
        customer.save()
        messages.success(request, "Cliente creado correctamente.")
        return redirect("customer-detail", pk=customer.pk)
    return render(
        request,
        "customers/form.html",
        {"organization": organization, "form": form, "title": "Nuevo cliente"},
    )


@login_required
@subscription_required
def customer_update(request, pk):
    organization = current_organization(request)
    customer = get_object_or_404(Customer.objects.for_organization(organization), pk=pk)
    form = CustomerForm(request.POST or None, instance=customer)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Cliente actualizado.")
        return redirect("customer-detail", pk=customer.pk)
    return render(
        request,
        "customers/form.html",
        {"organization": organization, "form": form, "title": "Editar cliente"},
    )


@login_required
@subscription_required
@require_POST
def customer_archive(request, pk):
    organization = current_organization(request)
    customer = get_object_or_404(Customer.objects.for_organization(organization), pk=pk)
    customer.is_active = not customer.is_active
    customer.save(update_fields=("is_active", "updated_at"))
    messages.success(request, "Estado del cliente actualizado.")
    return redirect("customer-detail", pk=customer.pk)


@login_required
@subscription_required
def vehicle_create(request, customer_pk):
    organization = current_organization(request)
    customer = get_object_or_404(
        Customer.objects.for_organization(organization), pk=customer_pk, is_active=True
    )
    form = VehicleForm(request.POST or None, organization=organization)
    if request.method == "POST" and form.is_valid():
        vehicle = form.save(commit=False)
        vehicle.organization = organization
        vehicle.customer = customer
        vehicle.full_clean()
        vehicle.save()
        messages.success(request, "Vehículo agregado.")
        return redirect("customer-detail", pk=customer.pk)
    return render(
        request,
        "customers/vehicle_form.html",
        {"customer": customer, "form": form, "title": "Nuevo vehículo"},
    )


@login_required
@subscription_required
def vehicle_update(request, pk):
    organization = current_organization(request)
    vehicle = get_object_or_404(
        Vehicle.objects.for_organization(organization).select_related("customer"),
        pk=pk,
    )
    form = VehicleForm(
        request.POST or None, instance=vehicle, organization=organization
    )
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Vehículo actualizado.")
        return redirect("customer-detail", pk=vehicle.customer_id)
    return render(
        request,
        "customers/vehicle_form.html",
        {"customer": vehicle.customer, "form": form, "title": "Editar vehículo"},
    )


@login_required
@subscription_required
@require_POST
def vehicle_archive(request, pk):
    organization = current_organization(request)
    vehicle = get_object_or_404(
        Vehicle.objects.for_organization(organization).select_related("customer"),
        pk=pk,
    )
    vehicle.is_active = not vehicle.is_active
    vehicle.save(update_fields=("is_active", "updated_at"))
    messages.success(request, "Estado del vehículo actualizado.")
    return redirect("customer-detail", pk=vehicle.customer_id)
