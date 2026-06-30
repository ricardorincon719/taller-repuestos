from io import BytesIO
from xml.sax.saxutils import escape

from django.conf import settings
from django.db import transaction
from django.utils import translation
from django.utils.translation import gettext as _
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from apps.organizations.models import Organization

from .models import Quote


@transaction.atomic
def create_quote(*, organization, customer, created_by, vehicle=None, **fields):
    locked_organization = Organization.objects.select_for_update().get(
        pk=organization.pk
    )
    number = locked_organization.next_quote_number
    locked_organization.next_quote_number = number + 1
    locked_organization.save(update_fields=("next_quote_number", "updated_at"))

    quote = Quote(
        organization=locked_organization,
        number=number,
        customer=customer,
        vehicle=vehicle,
        created_by=created_by,
        **fields,
    )
    quote.full_clean()
    quote.save()
    quote.recalculate_totals()
    return quote


def build_quote_pdf(quote):
    with translation.override(quote.organization.language):
        return _build_quote_pdf(quote)


def _build_quote_pdf(quote):
    output = BytesIO()
    document = SimpleDocTemplate(
        output,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title=quote.display_number,
        author=quote.organization.name,
    )
    styles = getSampleStyleSheet()

    organization_lines = [
        escape(quote.organization.get_business_type_display()),
        *[
            escape(value)
            for value in (
                quote.organization.phone,
                quote.organization.email,
                quote.organization.tax_id,
            )
            if value
        ],
    ]
    if quote.organization.address:
        organization_lines.append(escape(quote.organization.address).replace("\n", "<br/>"))

    story = [
        Paragraph(escape(quote.organization.name), styles["Title"]),
        Paragraph("<br/>".join(organization_lines), styles["BodyText"]),
        Spacer(1, 4 * mm),
        Paragraph(f"{escape(_('Presupuesto'))} {escape(quote.display_number)}", styles["Heading2"]),
        Spacer(1, 6 * mm),
        Paragraph(f"<b>{escape(_('Cliente'))}:</b> {escape(quote.customer.name)}", styles["BodyText"]),
    ]
    if quote.customer.phone:
        story.append(
            Paragraph(
                f"<b>{escape(_('Teléfono'))}:</b> {escape(quote.customer.phone)}",
                styles["BodyText"],
            )
        )
    if quote.customer.email:
        story.append(
            Paragraph(
                f"<b>Email:</b> {escape(quote.customer.email)}",
                styles["BodyText"],
            )
        )
    if quote.vehicle:
        story.append(
            Paragraph(f"<b>{escape(_('Vehículo'))}:</b> {escape(str(quote.vehicle))}", styles["BodyText"])
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
    if quote.valid_until:
        story.insert(
            -1,
            Paragraph(
                f"<b>{escape(_('Válido hasta'))}:</b> {quote.valid_until.strftime('%d/%m/%Y')}",
                styles["BodyText"],
            ),
        )

    rows = [[_("Descripción"), _("Cantidad"), _("Precio"), _("Total")]]
    for item in quote.items.all():
        rows.append(
            [
                Paragraph(escape(item.description), styles["BodyText"]),
                f"{item.quantity:.2f}",
                _money(item.unit_price),
                _money(item.total_amount),
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
            [_("Mano de obra"), _money(quote.labor_amount)],
            [_("Ítems"), _money(quote.items_amount)],
            [_("Descuento"), _money(quote.discount_amount)],
            [_("TOTAL"), _money(quote.total_amount)],
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

    if quote.notes:
        story.extend(
            [
                Spacer(1, 7 * mm),
                Paragraph(f"<b>{escape(_('Notas'))}</b>", styles["Heading3"]),
                Paragraph(escape(quote.notes).replace("\n", "<br/>"), styles["BodyText"]),
            ]
        )
    story.extend(
        [
            Spacer(1, 10 * mm),
            Paragraph(
                escape(getattr(settings, "QUOTE_PDF_FOOTER", _("Generado por Taller Pro"))),
                styles["Italic"],
            ),
        ]
    )
    document.build(story)
    return output.getvalue()


def _money(value):
    return f"R$ {value:.2f}"
