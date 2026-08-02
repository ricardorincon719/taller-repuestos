import re
from urllib.parse import quote as urlquote

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q
from django.http import Http404, HttpResponse, HttpResponseBadRequest
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import translation
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from apps.billing.decorators import subscription_required
from apps.accounts.security import hash_identifier, request_ip
from apps.organizations.formatting import format_money
from apps.organizations.models import Membership
from apps.organizations.services import get_request_membership

from .forms import QuoteForm, QuoteItemFormSet
from .models import Quote
from .services import (
    build_quote_pdf,
    change_quote_status,
    create_quote,
    duplicate_quote,
    record_quote_event,
    renew_public_share,
    revoke_public_share,
)


@login_required
@subscription_required
def quote_list(request):
    organization = get_request_membership(request).organization
    query = request.GET.get("q", "").strip()
    status = request.GET.get("estado", "").strip()
    show_archived = request.GET.get("archivados") == "1"
    quotes = (
        Quote.objects.for_organization(organization)
        .select_related("customer", "vehicle")
        .filter(is_archived=show_archived)
    )
    if query:
        number_query = query.rsplit("-", 1)[-1].lstrip("0")
        lookup = Q(customer__name__icontains=query) | Q(notes__icontains=query)
        if number_query.isdigit():
            lookup |= Q(number=int(number_query))
        quotes = quotes.filter(lookup)
    valid_statuses = {value for value, _label in Quote.Status.choices}
    if status in valid_statuses:
        quotes = quotes.filter(status=status)
    quotes = quotes.order_by("-created_at", "-pk")
    page_obj = Paginator(quotes, 25).get_page(request.GET.get("pagina"))
    return render(
        request,
        "quotes/list.html",
        {
            "organization": organization,
            "quotes": page_obj,
            "page_obj": page_obj,
            "query": query,
            "selected_status": status,
            "status_choices": Quote.Status.choices,
            "show_archived": show_archived,
        },
    )


@login_required
@subscription_required
def quote_detail(request, pk):
    organization = get_request_membership(request).organization
    quote = get_object_or_404(
        Quote.objects.for_organization(organization)
        .select_related("customer", "vehicle", "created_by")
        .prefetch_related("items"),
        pk=pk,
    )
    return render(
        request,
        "quotes/detail.html",
        {**_quote_context(request, quote), "events": quote.events.select_related("actor")[:20]},
    )


@login_required
@subscription_required
def quote_create(request):
    organization = get_request_membership(request).organization
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
                status=Quote.Status.DRAFT,
                labor_amount=data["labor_amount"],
                discount_amount=data["discount_amount"],
                valid_until=data.get("valid_until"),
                notes=data["notes"],
            )
            formset.instance = quote
            formset.save()
            quote.recalculate_totals()
        messages.success(request, _("Presupuesto %(number)s creado.") % {"number": quote.display_number})
        return redirect("quote-detail", pk=quote.pk)

    return render(
        request,
        "quotes/form.html",
        {"organization": organization, "form": form, "formset": formset},
    )


@login_required
@subscription_required
def quote_update(request, pk):
    organization = get_request_membership(request).organization
    quote = get_object_or_404(
        Quote.objects.for_organization(organization).prefetch_related("items"), pk=pk
    )
    if not quote.is_editable:
        messages.error(
            request,
            _("Solo se pueden editar borradores. Duplica el documento para corregir uno emitido."),
        )
        return redirect("quote-detail", pk=quote.pk)
    form = QuoteForm(request.POST or None, instance=quote, organization=organization)
    formset = QuoteItemFormSet(
        request.POST or None, instance=quote, prefix="items"
    )
    if request.method == "POST" and form.is_valid() and formset.is_valid():
        with transaction.atomic():
            quote = form.save()
            formset.save()
            quote.recalculate_totals()
            record_quote_event(quote, "quote.updated", actor=request.user)
        messages.success(request, _("Presupuesto actualizado."))
        return redirect("quote-detail", pk=quote.pk)
    return render(
        request,
        "quotes/form.html",
        {
            "organization": organization,
            "form": form,
            "formset": formset,
            "quote": quote,
            "editing": True,
        },
    )


@login_required
@subscription_required
@require_POST
def quote_status_update(request, pk):
    membership = get_request_membership(request)
    organization = membership.organization
    quote = get_object_or_404(Quote.objects.for_organization(organization), pk=pk)
    status = request.POST.get("status", "")
    valid_statuses = {value for value, _label in Quote.Status.choices}
    if status not in valid_statuses:
        return HttpResponseBadRequest(_("Estado inválido."))
    if status in {Quote.Status.INVOICED, Quote.Status.CANCELLED} and not membership.can_manage_business:
        return HttpResponseBadRequest(_("No tienes permisos para ese cambio de estado."))
    try:
        quote = change_quote_status(quote=quote, new_status=status, actor=request.user)
    except ValueError:
        return HttpResponseBadRequest(_("Transición de estado inválida."))
    messages.success(request, _("Estado del presupuesto actualizado."))
    return redirect("quote-detail", pk=quote.pk)


@login_required
@subscription_required
@require_POST
def quote_duplicate(request, pk):
    organization = get_request_membership(request).organization
    quote = get_object_or_404(
        Quote.objects.for_organization(organization).prefetch_related("items"), pk=pk
    )
    copy = duplicate_quote(quote=quote, created_by=request.user)
    messages.success(request, _("Se creó un nuevo borrador a partir del presupuesto."))
    return redirect("quote-update", pk=copy.pk)


@login_required
@subscription_required
@require_POST
def quote_share_update(request, pk):
    organization = get_request_membership(request).organization
    quote = get_object_or_404(Quote.objects.for_organization(organization), pk=pk)
    action = request.POST.get("action")
    if action == "revoke":
        revoke_public_share(quote, actor=request.user)
        messages.success(request, _("Enlace público revocado."))
    elif action == "renew":
        try:
            renew_public_share(quote, actor=request.user)
        except ValueError:
            return HttpResponseBadRequest(_("Solo se pueden compartir documentos emitidos."))
        messages.success(request, _("Se generó un enlace público nuevo."))
    else:
        return HttpResponseBadRequest(_("Acción inválida."))
    return redirect("quote-detail", pk=quote.pk)


@login_required
@subscription_required
@require_POST
def quote_archive(request, pk):
    membership = get_request_membership(request)
    if not membership.can_manage_business:
        return HttpResponseBadRequest(_("No tienes permisos para archivar."))
    quote = get_object_or_404(
        Quote.objects.for_organization(membership.organization), pk=pk
    )
    quote.is_archived = not quote.is_archived
    quote.public_access_enabled = False if quote.is_archived else quote.public_access_enabled
    quote.save(update_fields=("is_archived", "public_access_enabled", "updated_at"))
    record_quote_event(
        quote,
        "quote.archived" if quote.is_archived else "quote.restored",
        actor=request.user,
    )
    messages.success(request, _("Archivo de presupuesto actualizado."))
    return redirect("quote-detail", pk=quote.pk)


@login_required
@subscription_required
def quote_pdf(request, pk):
    organization = get_request_membership(request).organization
    quote = get_object_or_404(
        Quote.objects.for_organization(organization)
        .select_related("organization", "customer", "vehicle")
        .prefetch_related("items"),
        pk=pk,
    )
    return _pdf_response(quote)


def public_quote_detail(request, token):
    quote = _public_quote(token)
    with translation.override(quote.organization.language):
        request.LANGUAGE_CODE = translation.get_language()
        return render(
            request,
            "quotes/public_detail.html",
            _quote_context(request, quote),
        )


def public_quote_pdf(request, token):
    quote = _public_quote(token)
    with translation.override(quote.organization.language):
        return _pdf_response(quote)


@require_POST
def public_quote_decision(request, token):
    quote = _public_quote(token)
    decision = request.POST.get("decision")
    target = {
        "approve": Quote.Status.APPROVED,
        "reject": Quote.Status.REJECTED,
    }.get(decision)
    if target is None or quote.status != Quote.Status.SENT:
        return HttpResponseBadRequest(_("Esta decisión ya no está disponible."))
    try:
        quote = change_quote_status(
            quote=quote,
            new_status=target,
            metadata={
                "source": "public_quote",
                "ip_hash": hash_identifier(request_ip(request)),
            },
        )
    except ValueError:
        return HttpResponseBadRequest(_("Esta decisión ya no está disponible."))
    messages.success(request, _("Tu respuesta quedó registrada."))
    return redirect("public-quote-detail", token=quote.share_token)


def _public_quote(token):
    quote = get_object_or_404(
        Quote.objects.select_related("organization", "customer", "vehicle")
        .prefetch_related("items"),
        share_token=token,
        organization__is_active=True,
    )
    if not quote.public_is_available:
        raise Http404
    return quote


def _quote_context(request, quote):
    public_url = request.build_absolute_uri(
        reverse("public-quote-detail", args=(quote.share_token,))
    )
    message = _(
        "Hola %(customer)s, compartimos el presupuesto %(number)s por %(total)s: %(url)s"
    ) % {
        "customer": quote.customer.name,
        "number": quote.display_number,
        "total": _money(quote.total_amount, quote.currency),
        "url": public_url,
    }
    phone = re.sub(r"\D", "", quote.customer.phone)
    whatsapp_base = f"https://wa.me/{phone}" if phone else "https://wa.me/"
    membership = getattr(request, "current_membership", None)
    can_manage = bool(membership and membership.can_manage_business)
    return {
        "quote": quote,
        "organization": quote.organization,
        "public_url": public_url,
        "whatsapp_url": f"{whatsapp_base}?text={urlquote(message)}",
        "status_choices": [
            (value, label)
            for value, label in Quote.Status.choices
            if (value == quote.status or quote.can_transition_to(value))
            and (can_manage or value not in {Quote.Status.INVOICED, Quote.Status.CANCELLED})
        ],
        "document": quote.issue_snapshot,
    }


def _pdf_response(quote):
    response = HttpResponse(build_quote_pdf(quote), content_type="application/pdf")
    response["Content-Disposition"] = (
        f'attachment; filename="{quote.display_number}.pdf"'
    )
    response["X-Content-Type-Options"] = "nosniff"
    return response


def _money(value, currency="BRL"):
    return format_money(value, currency)
