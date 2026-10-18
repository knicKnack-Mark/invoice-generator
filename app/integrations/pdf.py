import io
import re
from xml.sax.saxutils import escape as xml_escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader
from reportlab.platypus import Image, SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet


def render_invoice_pdf(
    *,
    invoice,
    client_name: str,
    organization_name: str,
    profile=None,
    logo_bytes: bytes | None = None,
) -> bytes:
    """Renders a single invoice to a PDF and returns the raw bytes. Pure
    Python (reportlab), no external service/binary dependency — keeps PDF
    generation simple to run anywhere the backend runs, including inside a
    background worker later without extra infrastructure."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=0.75 * inch, bottomMargin=0.75 * inch)
    styles = getSampleStyleSheet()
    elements = []

    profile = profile or object()
    business_name = getattr(profile, "business_name", None) or organization_name
    business_address = getattr(profile, "business_address", None)
    business_email = getattr(profile, "business_email", None)
    business_phone = getattr(profile, "business_phone", None)
    tax_id = getattr(profile, "tax_id", None)
    template = getattr(profile, "invoice_template", "classic")
    brand_color = getattr(profile, "brand_color", None)
    if not isinstance(brand_color, str) or not re.fullmatch(r"#[0-9A-Fa-f]{6}", brand_color):
        brand_color = "#2d2d2d"
    accent = colors.HexColor(brand_color)

    profile_lines = [f"<b>{xml_escape(business_name)}</b>"]
    for value in (business_address, business_email, business_phone, f"Tax ID: {tax_id}" if tax_id else None):
        if value:
            profile_lines.append(xml_escape(value).replace("\n", "<br/>"))
    profile_paragraph = Paragraph("<br/>".join(profile_lines), styles["Normal"])
    if logo_bytes:
        logo = Image(ImageReader(io.BytesIO(logo_bytes)), width=1.4 * inch, height=0.8 * inch, kind="proportional")
        header = Table([[profile_paragraph, logo]], colWidths=[4.6 * inch, 1.4 * inch])
        header.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("ALIGN", (1, 0), (1, 0), "RIGHT")]))
        elements.append(header)
    else:
        elements.append(profile_paragraph)
    elements.append(Spacer(1, 14))

    title_style = styles["Title"]
    title_style.textColor = accent
    if template == "minimal":
        title_style.fontSize = 17
        title_style.alignment = 0
    elif template == "modern":
        title_style.fontSize = 24
        title_style.alignment = 2
    elements.append(Paragraph(f"INVOICE {xml_escape(invoice.invoice_number)}", title_style))
    elements.append(Spacer(1, 12))
    elements.append(Paragraph(f"<b>Bill To:</b> {xml_escape(client_name)}", styles["Normal"]))
    elements.append(Paragraph(f"<b>Invoice Date:</b> {invoice.invoice_date.isoformat()}", styles["Normal"]))
    elements.append(Paragraph(f"<b>Due Date:</b> {invoice.due_date.isoformat()}", styles["Normal"]))
    elements.append(Paragraph(f"<b>Status:</b> {xml_escape(invoice.status.value)}{' (OVERDUE)' if invoice.is_overdue else ''}", styles["Normal"]))
    elements.append(Spacer(1, 20))

    table_data = [["Description", "Qty", "Unit Price", "Discount", "Tax", "Total"]]
    for item in invoice.items:
        table_data.append([
            xml_escape(item.description), str(item.quantity), f"{item.unit_price:.2f}",
            f"{item.discount:.2f}", f"{item.tax:.2f}", f"{item.total:.2f}",
        ])
    for exp_link in invoice.expenses:
        table_data.append(["Expense (attached)", "1", f"{exp_link.amount:.2f}", "0.00", "0.00", f"{exp_link.amount:.2f}"])

    for time_link in getattr(invoice, "time_entries", []):
        table_data.append(["Time (attached)", "1", f"{time_link.amount:.2f}", "0.00", "0.00", f"{time_link.amount:.2f}"])

    table = Table(table_data, colWidths=[2.4 * inch, 0.6 * inch, 1 * inch, 0.8 * inch, 0.7 * inch, 1 * inch])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), accent),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f5f5")]),
    ]))
    elements.append(table)
    elements.append(Spacer(1, 16))

    totals_data = [
        ["Subtotal", f"{invoice.currency} {invoice.subtotal:.2f}"],
        ["Discount", f"{invoice.currency} {invoice.discount_total:.2f}"],
        ["Tax", f"{invoice.currency} {invoice.tax_total:.2f}"],
        ["Total", f"{invoice.currency} {invoice.total:.2f}"],
        ["Paid", f"{invoice.currency} {invoice.amount_paid:.2f}"],
        ["Balance Due", f"{invoice.currency} {invoice.balance_due:.2f}"],
    ]
    totals_table = Table(totals_data, colWidths=[4.5 * inch, 1.5 * inch])
    totals_table.setStyle(TableStyle([
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("FONTNAME", (0, 3), (-1, 3), "Helvetica-Bold"),
        ("FONTNAME", (0, 5), (-1, 5), "Helvetica-Bold"),
        ("LINEABOVE", (0, 3), (-1, 3), 0.5, colors.grey),
    ]))
    elements.append(totals_table)

    bank_info = getattr(profile, "bank_info", None) or {}
    bank_details = [
        (label, bank_info.get(key))
        for key, label in (
            ("bank_name", "Bank"),
            ("account_name", "Account name"),
            ("account_number", "Account number"),
            ("routing_or_swift", "Routing / SWIFT"),
        )
        if bank_info.get(key)
    ]
    if bank_details:
        elements.append(Spacer(1, 18))
        elements.append(Paragraph("<b>Payment Details</b>", styles["Heading3"]))
        for label, value in bank_details:
            elements.append(Paragraph(f"<b>{label}:</b> {xml_escape(str(value))}", styles["Normal"]))

    if invoice.notes:
        elements.append(Spacer(1, 20))
        elements.append(Paragraph(f"<b>Notes:</b> {xml_escape(invoice.notes)}", styles["Normal"]))
    if invoice.terms:
        elements.append(Spacer(1, 10))
        elements.append(Paragraph(f"<b>Terms:</b> {xml_escape(invoice.terms)}", styles["Normal"]))
    if getattr(profile, "footer_text", None):
        elements.append(Spacer(1, 18))
        elements.append(Paragraph(xml_escape(profile.footer_text), styles["Italic"]))

    doc.build(elements)
    return buffer.getvalue()
