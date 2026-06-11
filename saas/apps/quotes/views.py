import re
from urllib.parse import quote as urlquote

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from apps.billing.decorators import subscription_required
from apps.organizations.services import get_current_membership

from .forms import QuoteForm, QuoteItemFormSet
from .models import Quote
from .services import build_quote_pdf, create_quote


@login_required
@subscription_required
def quote_list(request):
    organization = get_current_membership(request.user).organization
    quotes = (
        Quote.objects.for_organization(organization)
        .select_related("customer", "vehicle")
        .all()
    )
    return render(
        request,
        "quotes/list.html",
        {"organization": organization, "quotes": quotes},
    )


@login_required
@subscription_required
def quote_detail(request, pk):
    organization = get_current_membership(request.user).organization
    quote = get_object_or_404(
        Quote.objects.for_organization(organization)
        .select_related("customer", "vehicle", "created_by")
        .prefetch_related("items"),
        pk=pk,
    )
    return render(
        request,
        "quotes/detail.html",
        _quote_context(request, quote),
    )


@login_required
@subscription_required
def quote_create(request):
    organization = get_current_membership(request.user).organization
    form = QuoteForm(request.POST or None, organization=organization)
    form.instance.organization = organization
    form.instance.created_by = request.user
    formset = QuoteItemFormSet(request.POST or None, prefix="items")

    if request.method == "POST" and form.is_valid() and formset.is_valid():
        data = form.cleaned_data
        with transaction.atomic():
            quote = create_quote(
                organization=organization,
                customer=data["customer"],
                vehicle=data.get("vehicle"),
                created_by=request.user,
                status=data["status"],
                labor_amount=data["labor_amount"],
                discount_amount=data["discount_amount"],
                valid_until=data.get("valid_until"),
                notes=data["notes"],
            )
            formset.instance = quote
            formset.save()
            quote.recalculate_totals()
        messages.success(request, f"Presupuesto {quote.display_number} creado.")
        return redirect("quote-detail", pk=quote.pk)

    return render(
        request,
        "quotes/form.html",
        {"organization": organization, "form": form, "formset": formset},
    )


@login_required
@subscription_required
@require_POST
def quote_status_update(request, pk):
    organization = get_current_membership(request.user).organization
    quote = get_object_or_404(Quote.objects.for_organization(organization), pk=pk)
    status = request.POST.get("status", "")
    valid_statuses = {value for value, _label in Quote.Status.choices}
    if status not in valid_statuses:
        return HttpResponseBadRequest("Estado inválido.")
    quote.status = status
    quote.save(update_fields=("status", "updated_at"))
    messages.success(request, "Estado del presupuesto actualizado.")
    return redirect("quote-detail", pk=quote.pk)


@login_required
@subscription_required
def quote_pdf(request, pk):
    organization = get_current_membership(request.user).organization
    quote = get_object_or_404(
        Quote.objects.for_organization(organization)
        .select_related("organization", "customer", "vehicle")
        .prefetch_related("items"),
        pk=pk,
    )
    return _pdf_response(quote)


def public_quote_detail(request, token):
    quote = _public_quote(token)
    return render(
        request,
        "quotes/public_detail.html",
        _quote_context(request, quote),
    )


def public_quote_pdf(request, token):
    return _pdf_response(_public_quote(token))


def _public_quote(token):
    return get_object_or_404(
        Quote.objects.select_related("organization", "customer", "vehicle")
        .prefetch_related("items"),
        share_token=token,
        organization__is_active=True,
    )


def _quote_context(request, quote):
    public_url = request.build_absolute_uri(
        reverse("public-quote-detail", args=(quote.share_token,))
    )
    message = (
        f"Hola {quote.customer.name}, compartimos el presupuesto "
        f"{quote.display_number} por {_money(quote.total_amount)}: {public_url}"
    )
    phone = re.sub(r"\D", "", quote.customer.phone)
    whatsapp_base = f"https://wa.me/{phone}" if phone else "https://wa.me/"
    return {
        "quote": quote,
        "public_url": public_url,
        "whatsapp_url": f"{whatsapp_base}?text={urlquote(message)}",
        "status_choices": Quote.Status.choices,
    }


def _pdf_response(quote):
    response = HttpResponse(build_quote_pdf(quote), content_type="application/pdf")
    response["Content-Disposition"] = (
        f'attachment; filename="{quote.display_number}.pdf"'
    )
    response["X-Content-Type-Options"] = "nosniff"
    return response


def _money(value):
    return f"R$ {value:.2f}"
