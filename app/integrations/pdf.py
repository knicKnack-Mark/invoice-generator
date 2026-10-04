import io

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet


def render_invoice_pdf(*, invoice, client_name: str) -> bytes:
    """Renders a single invoice to a PDF and returns the raw bytes. Pure
    Python (reportlab), no external service/binary dependency — keeps PDF
    generation simple to run anywhere the backend runs, including inside a
    background worker later without extra infrastructure."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=0.75 * inch, bottomMargin=0.75 * inch)
    styles = getSampleStyleSheet()
    elements = []

    elements.append(Paragraph(f"INVOICE {invoice.invoice_number}", styles["Title"]))
    elements.append(Spacer(1, 12))
    elements.append(Paragraph(f"<b>Bill To:</b> {client_name}", styles["Normal"]))
    elements.append(Paragraph(f"<b>Invoice Date:</b> {invoice.invoice_date.isoformat()}", styles["Normal"]))
    elements.append(Paragraph(f"<b>Due Date:</b> {invoice.due_date.isoformat()}", styles["Normal"]))
    elements.append(Paragraph(f"<b>Status:</b> {invoice.status.value}{' (OVERDUE)' if invoice.is_overdue else ''}", styles["Normal"]))
    elements.append(Spacer(1, 20))

    table_data = [["Description", "Qty", "Unit Price", "Discount", "Tax", "Total"]]
    for item in invoice.items:
        table_data.append([
            item.description, str(item.quantity), f"{item.unit_price:.2f}",
            f"{item.discount:.2f}", f"{item.tax:.2f}", f"{item.total:.2f}",
        ])
    for exp_link in invoice.expenses:
        table_data.append(["Expense (attached)", "1", f"{exp_link.amount:.2f}", "0.00", "0.00", f"{exp_link.amount:.2f}"])

    table = Table(table_data, colWidths=[2.4 * inch, 0.6 * inch, 1 * inch, 0.8 * inch, 0.7 * inch, 1 * inch])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2d2d2d")),
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

    if invoice.notes:
        elements.append(Spacer(1, 20))
        elements.append(Paragraph(f"<b>Notes:</b> {invoice.notes}", styles["Normal"]))
    if invoice.terms:
        elements.append(Spacer(1, 10))
        elements.append(Paragraph(f"<b>Terms:</b> {invoice.terms}", styles["Normal"]))

    doc.build(elements)
    return buffer.getvalue()
