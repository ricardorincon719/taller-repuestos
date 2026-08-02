from io import BytesIO
import uuid
from datetime import date, timedelta
from xml.sax.saxutils import escape

from django.conf import settings
from django.db import transaction
from django.utils import timezone, translation
from django.utils.translation import gettext as _
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from apps.organizations.formatting import format_money
from apps.organizations.models import Organization

from .models import Quote, QuoteEvent, QuoteItem


@transaction.atomic
def create_quote(*, organization, customer, created_by, vehicle=None, source_quote=None, **fields):
    locked_organization = Organization.objects.select_for_update().get(
        pk=organization.pk
    )
    number = locked_organization.next_quote_number
    locked_organization.next_quote_number = number + 1
    locked_organization.save(update_fields=("next_quote_number", "updated_at"))

    quote = Quote(
        organization=locked_organization,
        number=number,
        number_prefix=locked_organization.quote_prefix,
        currency=locked_organization.currency,
        share_expires_at=timezone.now()
        + timedelta(days=locked_organization.public_quote_valid_days),
        customer=customer,
        vehicle=vehicle,
        created_by=created_by,
        source_quote=source_quote,
        **fields,
    )
    quote.full_clean()
    quote.save()
    quote.recalculate_totals()
    record_quote_event(quote, "quote.created", actor=created_by)
    return quote


def record_quote_event(
    quote, event_type, *, actor=None, from_status="", to_status="", metadata=None
):
    return QuoteEvent.objects.create(
        quote=quote,
        actor=actor,
        event_type=event_type,
        from_status=from_status,
        to_status=to_status,
        metadata=metadata or {},
    )


def build_issue_snapshot(quote):
    organization = quote.organization
    return {
        "organization": {
            "name": organization.name,
            "legal_name": organization.legal_name,
            "business_type": organization.business_type,
            "phone": organization.phone,
            "email": organization.email,
            "tax_id": organization.tax_id,
            "address": organization.address,
            "city": organization.city,
            "country": organization.country,
            "terms": organization.default_quote_terms,
            "warranty": organization.default_warranty_text,
            "payment_terms": organization.default_payment_terms,
            "footer": organization.default_footer,
        },
        "customer": {
            "name": quote.customer.name,
            "phone": quote.customer.phone,
            "email": quote.customer.email,
            "tax_id": quote.customer.tax_id,
            "address": quote.customer.address,
        },
        "vehicle": str(quote.vehicle) if quote.vehicle else "",
        "items": [
            {
                "description": item.description,
                "quantity": str(item.quantity),
                "unit_price": str(item.unit_price),
                "total_amount": str(item.total_amount),
            }
            for item in quote.items.all()
        ],
        "amounts": {
            "labor": str(quote.labor_amount),
            "items": str(quote.items_amount),
            "discount": str(quote.discount_amount),
            "total": str(quote.total_amount),
        },
        "notes": quote.notes,
        "valid_until": quote.valid_until.isoformat() if quote.valid_until else "",
        "currency": quote.currency,
        "number": quote.display_number,
    }


@transaction.atomic
def change_quote_status(*, quote, new_status, actor=None, metadata=None):
    quote = Quote.objects.select_for_update(of=("self",)).select_related(
        "organization", "customer", "vehicle"
    ).prefetch_related("items").get(pk=quote.pk)
    old_status = quote.status
    if not quote.can_transition_to(new_status):
        raise ValueError("Invalid quote status transition")
    if new_status == old_status:
        return quote
    if old_status == Quote.Status.DRAFT and new_status != Quote.Status.CANCELLED:
        quote.issue_snapshot = build_issue_snapshot(quote)
        quote.issued_at = timezone.now()
        quote.public_access_enabled = True
        if not quote.share_expires_at or quote.share_expires_at <= timezone.now():
            quote.share_expires_at = timezone.now() + timedelta(
                days=quote.organization.public_quote_valid_days
            )
    if new_status == Quote.Status.CANCELLED:
        quote.public_access_enabled = False
    quote.status = new_status
    quote.save(
        update_fields=(
            "status",
            "issue_snapshot",
            "issued_at",
            "public_access_enabled",
            "share_expires_at",
            "updated_at",
        )
    )
    record_quote_event(
        quote,
        "quote.status_changed",
        actor=actor,
        from_status=old_status,
        to_status=new_status,
        metadata=metadata,
    )
    return quote


@transaction.atomic
def duplicate_quote(*, quote, created_by):
    duplicate = create_quote(
        organization=quote.organization,
        customer=quote.customer,
        vehicle=quote.vehicle,
        created_by=created_by,
        source_quote=quote,
        labor_amount=quote.labor_amount,
        discount_amount=quote.discount_amount,
        valid_until=quote.valid_until,
        notes=quote.notes,
        status=Quote.Status.DRAFT,
    )
    QuoteItem.objects.bulk_create(
        [
            QuoteItem(
                quote=duplicate,
                description=item.description,
                quantity=item.quantity,
                unit_price=item.unit_price,
                position=item.position,
            )
            for item in quote.items.all()
        ]
    )
    duplicate.recalculate_totals()
    record_quote_event(
        duplicate,
        "quote.duplicated",
        actor=created_by,
        metadata={"source_quote_id": quote.pk},
    )
    return duplicate


def renew_public_share(quote, *, actor):
    if quote.issued_at is None or quote.status in {
        Quote.Status.DRAFT,
        Quote.Status.CANCELLED,
    }:
        raise ValueError("Only issued, non-cancelled quotes can be shared")
    quote.share_token = uuid.uuid4()
    quote.public_access_enabled = True
    quote.share_expires_at = timezone.now() + timedelta(
        days=quote.organization.public_quote_valid_days
    )
    quote.save(
        update_fields=("share_token", "public_access_enabled", "share_expires_at", "updated_at")
    )
    record_quote_event(quote, "quote.share_renewed", actor=actor)
    return quote


def revoke_public_share(quote, *, actor):
    quote.public_access_enabled = False
    quote.save(update_fields=("public_access_enabled", "updated_at"))
    record_quote_event(quote, "quote.share_revoked", actor=actor)
    return quote


def build_quote_pdf(quote):
    with translation.override(quote.organization.language):
        return _build_quote_pdf(quote)


def _build_quote_pdf(quote):
    snapshot = quote.issue_snapshot or {}
    organization_data = snapshot.get("organization", {})
    customer_data = snapshot.get("customer", {})
    organization_name = organization_data.get("name", quote.organization.name)
    business_type_code = organization_data.get(
        "business_type", quote.organization.business_type
    )
    try:
        business_type = Organization.BusinessType(business_type_code).label
    except ValueError:
        business_type = business_type_code
    organization_phone = organization_data.get("phone", quote.organization.phone)
    organization_email = organization_data.get("email", quote.organization.email)
    organization_tax_id = organization_data.get("tax_id", quote.organization.tax_id)
    organization_address = organization_data.get("address", quote.organization.address)
    organization_city = organization_data.get("city", quote.organization.city)
    customer_name = customer_data.get("name", quote.customer.name)
    customer_phone = customer_data.get("phone", quote.customer.phone)
    customer_email = customer_data.get("email", quote.customer.email)
    vehicle_display = snapshot.get("vehicle") or (str(quote.vehicle) if quote.vehicle else "")
    currency = snapshot.get("currency", quote.currency)
    amounts = snapshot.get("amounts", {})
    labor_amount = amounts.get("labor", quote.labor_amount)
    items_amount = amounts.get("items", quote.items_amount)
    discount_amount = amounts.get("discount", quote.discount_amount)
    total_amount = amounts.get("total", quote.total_amount)
    notes = snapshot.get("notes", quote.notes)
    valid_until = snapshot.get("valid_until") or quote.valid_until
    if isinstance(valid_until, str):
        try:
            valid_until = date.fromisoformat(valid_until)
        except ValueError:
            valid_until = quote.valid_until
    item_rows = snapshot.get("items") or [
        {
            "description": item.description,
            "quantity": item.quantity,
            "unit_price": item.unit_price,
            "total_amount": item.total_amount,
        }
        for item in quote.items.all()
    ]
    output = BytesIO()
    document = SimpleDocTemplate(
        output,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title=quote.display_number,
        author=organization_name,
    )
    styles = getSampleStyleSheet()

    organization_lines = [
        escape(business_type),
        *[
            escape(value)
            for value in (
                organization_phone,
                organization_email,
                organization_tax_id,
            )
            if value
        ],
    ]
    legal_name = organization_data.get("legal_name", quote.organization.legal_name)
    if legal_name and legal_name != organization_name:
        organization_lines.insert(0, escape(legal_name))
    location = ", ".join(value for value in (organization_address, organization_city) if value)
    if location:
        organization_lines.append(escape(location).replace("\n", "<br/>"))

    story = []
    if quote.organization.has_logo:
        logo = Image(BytesIO(bytes(quote.organization.logo_data)))
        logo._restrictSize(50 * mm, 25 * mm)
        story.extend([logo, Spacer(1, 3 * mm)])
    story.extend([
        Paragraph(escape(organization_name), styles["Title"]),
        Paragraph("<br/>".join(organization_lines), styles["BodyText"]),
        Spacer(1, 4 * mm),
        Paragraph(f"{escape(_('Presupuesto'))} {escape(quote.display_number)}", styles["Heading2"]),
        Spacer(1, 6 * mm),
        Paragraph(f"<b>{escape(_('Cliente'))}:</b> {escape(customer_name)}", styles["BodyText"]),
    ])
    if customer_phone:
        story.append(
            Paragraph(
                f"<b>{escape(_('Teléfono'))}:</b> {escape(customer_phone)}",
                styles["BodyText"],
            )
        )
    if customer_email:
        story.append(
            Paragraph(
                f"<b>Email:</b> {escape(customer_email)}",
                styles["BodyText"],
            )
        )
    if vehicle_display:
        story.append(
            Paragraph(f"<b>{escape(_('Vehículo'))}:</b> {escape(vehicle_display)}", styles["BodyText"])
        )
    story.extend(
        [
            Paragraph(
                f"<b>{escape(_('Estado'))}:</b> {escape(quote.get_status_display())}",
                styles["BodyText"],
            ),
            Paragraph(
                f"<b>{escape(_('Fecha'))}:</b> {quote.created_at.astimezone().strftime('%d/%m/%Y')}",
                styles["BodyText"],
            ),
            Spacer(1, 6 * mm),
        ]
    )
    if valid_until:
        story.insert(
            -1,
            Paragraph(
                f"<b>{escape(_('Válido hasta'))}:</b> {valid_until.strftime('%d/%m/%Y')}",
                styles["BodyText"],
            ),
        )

    rows = [[_("Descripción"), _("Cantidad"), _("Precio"), _("Total")]]
    for item in item_rows:
        rows.append(
            [
                Paragraph(escape(str(item["description"])), styles["BodyText"]),
                f"{float(item['quantity']):.2f}",
                _money(item["unit_price"], currency),
                _money(item["total_amount"], currency),
            ]
        )
    if len(rows) == 1:
        rows.append([_("Sin ítems adicionales"), "-", "-", "-"])

    items_table = Table(rows, colWidths=(86 * mm, 25 * mm, 31 * mm, 31 * mm))
    items_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#155eef")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#dde3ed")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
                ("TOPPADDING", (0, 0), (-1, 0), 8),
            ]
        )
    )
    story.extend([items_table, Spacer(1, 7 * mm)])

    totals = Table(
        [
            [_("Mano de obra"), _money(labor_amount, currency)],
            [_("Ítems"), _money(items_amount, currency)],
            [_("Descuento"), _money(discount_amount, currency)],
            [_("TOTAL"), _money(total_amount, currency)],
        ],
        colWidths=(45 * mm, 35 * mm),
        hAlign="RIGHT",
    )
    totals.setStyle(
        TableStyle(
            [
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                ("LINEABOVE", (0, -1), (-1, -1), 1, colors.HexColor("#172033")),
                ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                ("TOPPADDING", (0, -1), (-1, -1), 8),
            ]
        )
    )
    story.append(totals)

    if notes:
        story.extend(
            [
                Spacer(1, 7 * mm),
                Paragraph(f"<b>{escape(_('Notas'))}</b>", styles["Heading3"]),
                Paragraph(escape(notes).replace("\n", "<br/>"), styles["BodyText"]),
            ]
        )
    for heading, value in (
        (_("Condiciones"), organization_data.get("terms", quote.organization.default_quote_terms)),
        (_("Garantía"), organization_data.get("warranty", quote.organization.default_warranty_text)),
        (_("Condiciones de pago"), organization_data.get("payment_terms", quote.organization.default_payment_terms)),
    ):
        if value:
            story.extend(
                [
                    Spacer(1, 5 * mm),
                    Paragraph(f"<b>{escape(heading)}</b>", styles["Heading3"]),
                    Paragraph(escape(value).replace("\n", "<br/>"), styles["BodyText"]),
                ]
            )
    story.extend(
        [
            Spacer(1, 10 * mm),
            Paragraph(
                escape(
                    organization_data.get("footer")
                    or quote.organization.default_footer
                    or getattr(settings, "QUOTE_PDF_FOOTER", _("Generado por Taller Pro"))
                ),
                styles["Italic"],
            ),
        ]
    )
    document.build(story)
    return output.getvalue()


def _money(value, currency="BRL"):
    return format_money(value, currency)
