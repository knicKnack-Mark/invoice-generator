from datetime import date
from html import escape
from re import fullmatch

from app.models.client import Client
from app.models.invoice import Invoice
from app.models.settings import OrganizationSettings


def password_reset_email(*, app_name: str, reset_url: str, expiry_minutes: int) -> str:
    safe_app_name = escape(app_name)
    safe_reset_url = escape(reset_url, quote=True)
    return f"""\
<!doctype html>
<html lang="en">
  <body style="margin:0;padding:0;background:#f1f5f4;color:#263238;font-family:Arial,Helvetica,sans-serif;">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="padding:36px 16px;background:#f1f5f4;">
      <tr><td align="center">
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:560px;background:#ffffff;border:1px solid #dce7e3;border-radius:10px;">
          <tr><td style="padding:30px 36px 12px;">
            <p style="margin:0;color:#5b8f82;font-size:13px;font-weight:700;letter-spacing:1px;text-transform:uppercase;">{safe_app_name}</p>
            <h1 style="margin:18px 0 10px;font-size:25px;line-height:1.3;color:#24342f;">Reset your password</h1>
            <p style="margin:0;color:#53615d;font-size:15px;line-height:1.7;">We received a request to reset the password for your account. Use the button below to choose a new password.</p>
          </td></tr>
          <tr><td align="center" style="padding:26px 36px;">
            <a href="{safe_reset_url}" style="display:inline-block;padding:14px 26px;border-radius:5px;background:#5b8f82;color:#ffffff;font-size:15px;font-weight:700;text-decoration:none;">Reset password</a>
          </td></tr>
          <tr><td style="padding:0 36px 28px;">
            <p style="margin:0 0 14px;color:#53615d;font-size:14px;line-height:1.7;">This link expires in {int(expiry_minutes)} minutes. If you did not request a password reset, you can safely ignore this email; your password will not change.</p>
            <p style="margin:0;color:#87918d;font-size:12px;line-height:1.6;">If the button does not work, copy and paste this address into your browser:<br><span style="color:#5b8f82;word-break:break-all;">{safe_reset_url}</span></p>
          </td></tr>
        </table>
        <p style="margin:18px 0 0;color:#89938f;font-size:12px;">This is an automated account-security message from {safe_app_name}.</p>
      </td></tr>
    </table>
  </body>
</html>"""


def invoice_email(
    *,
    invoice: Invoice,
    client: Client,
    organization_name: str,
    profile: OrganizationSettings | None = None,
) -> str:
    profile = profile or object()
    business_name = getattr(profile, "business_name", None) or organization_name
    brand_color = getattr(profile, "brand_color", None)
    if not isinstance(brand_color, str) or not fullmatch(r"#[0-9A-Fa-f]{6}", brand_color):
        brand_color = "#5b8f82"

    def money(value) -> str:
        return f"{escape(invoice.currency)} {value:,.2f}"

    def paragraph(value: str | None) -> str:
        if not value:
            return ""
        return f'<p style="margin:5px 0;color:#53615d;font-size:13px;line-height:1.6;">{escape(value).replace(chr(10), "<br>")}</p>'

    rows = []
    for item in invoice.items:
        rows.append(
            "<tr>"
            f'<td style="padding:11px 9px;border-bottom:1px solid #e4ebe8;color:#34413c;">{escape(item.description)}</td>'
            f'<td align="right" style="padding:11px 9px;border-bottom:1px solid #e4ebe8;color:#34413c;">{item.quantity:,.2f}</td>'
            f'<td align="right" style="padding:11px 9px;border-bottom:1px solid #e4ebe8;color:#34413c;">{money(item.unit_price)}</td>'
            f'<td align="right" style="padding:11px 9px;border-bottom:1px solid #e4ebe8;color:#34413c;">{money(item.total)}</td>'
            "</tr>"
        )
    for linked in invoice.expenses:
        rows.append(
            "<tr>"
            '<td style="padding:11px 9px;border-bottom:1px solid #e4ebe8;color:#34413c;">Expense</td>'
            '<td align="right" style="padding:11px 9px;border-bottom:1px solid #e4ebe8;color:#34413c;">1.00</td>'
            f'<td align="right" style="padding:11px 9px;border-bottom:1px solid #e4ebe8;color:#34413c;">{money(linked.amount)}</td>'
            f'<td align="right" style="padding:11px 9px;border-bottom:1px solid #e4ebe8;color:#34413c;">{money(linked.amount)}</td>'
            "</tr>"
        )
    for linked in getattr(invoice, "time_entries", []):
        rows.append(
            "<tr>"
            '<td style="padding:11px 9px;border-bottom:1px solid #e4ebe8;color:#34413c;">Time</td>'
            '<td align="right" style="padding:11px 9px;border-bottom:1px solid #e4ebe8;color:#34413c;">1.00</td>'
            f'<td align="right" style="padding:11px 9px;border-bottom:1px solid #e4ebe8;color:#34413c;">{money(linked.amount)}</td>'
            f'<td align="right" style="padding:11px 9px;border-bottom:1px solid #e4ebe8;color:#34413c;">{money(linked.amount)}</td>'
            "</tr>"
        )

    payment_details = getattr(profile, "bank_info", None) or {}
    bank_labels = {
        "bank_name": "Bank",
        "account_name": "Account name",
        "account_number": "Account number",
        "routing_or_swift": "Routing / SWIFT",
    }
    bank_rows = "".join(
        f'<p style="margin:4px 0;color:#53615d;font-size:13px;"><strong>{label}:</strong> {escape(str(payment_details[key]))}</p>'
        for key, label in bank_labels.items()
        if payment_details.get(key)
    )
    due_date = invoice.due_date.isoformat()
    if invoice.balance_due <= 0:
        due_label = "Paid in full" if invoice.amount_paid > 0 else "No balance due"
    else:
        due_label = f"Payment is due by {due_date}"
    footer = getattr(profile, "footer_text", None)
    terms = invoice.terms or ""

    return f"""\
<!doctype html>
<html lang="en">
  <body style="margin:0;padding:0;background:#eef4f2;color:#26332f;font-family:Arial,Helvetica,sans-serif;">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="padding:28px 12px;background:#eef4f2;">
      <tr><td align="center">
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:680px;background:#ffffff;border:1px solid #dce7e3;border-radius:8px;">
          <tr><td style="padding:30px 34px 16px;">
            <table role="presentation" width="100%" cellspacing="0" cellpadding="0"><tr>
              <td style="vertical-align:top;">
                <p style="margin:0 0 6px;color:#26332f;font-size:17px;font-weight:700;">{escape(business_name)}</p>
                {paragraph(getattr(profile, "business_address", None))}
                {paragraph(getattr(profile, "business_email", None))}
                {paragraph(getattr(profile, "business_phone", None))}
              </td>
              <td align="right" style="vertical-align:top;color:{brand_color};font-size:27px;font-weight:700;letter-spacing:3px;">INVOICE</td>
            </tr></table>
          </td></tr>
          <tr><td style="padding:8px 34px 22px;">
            <table role="presentation" width="100%" cellspacing="0" cellpadding="0"><tr>
              <td style="vertical-align:top;width:55%;">
                <p style="margin:0 0 8px;color:{brand_color};font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:.5px;">Bill to</p>
                <p style="margin:0 0 5px;color:#26332f;font-size:15px;font-weight:700;">{escape(client.name)}</p>
                {paragraph(getattr(client, "company_name", None))}
                {paragraph(getattr(client, "address", None))}
              </td>
              <td align="right" style="vertical-align:top;">
                <p style="margin:2px 0;color:#53615d;font-size:13px;"><strong style="color:{brand_color};">Invoice #</strong> &nbsp; {escape(invoice.invoice_number)}</p>
                <p style="margin:8px 0;color:#53615d;font-size:13px;"><strong style="color:{brand_color};">Invoice date</strong> &nbsp; {invoice.invoice_date.isoformat()}</p>
                <p style="margin:8px 0;color:#53615d;font-size:13px;"><strong style="color:{brand_color};">Due date</strong> &nbsp; {due_date}</p>
              </td>
            </tr></table>
          </td></tr>
          <tr><td style="padding:0 34px;">
            <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="border-collapse:collapse;font-size:13px;">
              <thead><tr style="background:{brand_color};color:#ffffff;">
                <th align="left" style="padding:11px 9px;">Description</th>
                <th align="right" style="padding:11px 9px;">Qty</th>
                <th align="right" style="padding:11px 9px;">Unit price</th>
                <th align="right" style="padding:11px 9px;">Amount</th>
              </tr></thead>
              <tbody>{''.join(rows)}</tbody>
            </table>
          </td></tr>
          <tr><td align="right" style="padding:18px 34px 8px;">
            <table role="presentation" width="280" cellspacing="0" cellpadding="0" style="border-collapse:collapse;margin-left:auto;font-size:13px;">
              <tr><td style="padding:6px 8px;color:#53615d;">Subtotal</td><td align="right" style="padding:6px 8px;color:#26332f;">{money(invoice.subtotal)}</td></tr>
              <tr><td style="padding:6px 8px;color:#53615d;">Discount</td><td align="right" style="padding:6px 8px;color:#26332f;">-{money(invoice.discount_total)}</td></tr>
              <tr><td style="padding:6px 8px;color:#53615d;">Tax</td><td align="right" style="padding:6px 8px;color:#26332f;">{money(invoice.tax_total)}</td></tr>
              <tr><td style="padding:9px 8px;border-top:1px solid {brand_color};color:{brand_color};font-weight:700;">Total</td><td align="right" style="padding:9px 8px;border-top:1px solid {brand_color};color:{brand_color};font-weight:700;">{money(invoice.total)}</td></tr>
              <tr><td style="padding:6px 8px;color:#53615d;">Paid</td><td align="right" style="padding:6px 8px;color:#26332f;">{money(invoice.amount_paid)}</td></tr>
              <tr><td style="padding:9px 8px;background:#f2f7f5;color:{brand_color};font-weight:700;">Balance due</td><td align="right" style="padding:9px 8px;background:#f2f7f5;color:{brand_color};font-weight:700;">{money(invoice.balance_due)}</td></tr>
            </table>
          </td></tr>
          <tr><td style="padding:24px 34px 30px;">
            <p style="margin:0 0 10px;color:{brand_color};font-size:13px;font-weight:700;">{escape(due_label)}</p>
            {f'<p style="margin:5px 0;color:#53615d;font-size:13px;line-height:1.6;"><strong>Terms:</strong> {escape(terms)}</p>' if terms else ''}
            {bank_rows}
            {f'<p style="margin:16px 0 0;color:#53615d;font-size:13px;line-height:1.6;">{escape(footer)}</p>' if footer else ''}
            <p style="margin:18px 0 0;color:#53615d;font-size:13px;line-height:1.6;">The invoice PDF is attached for your records. Please contact us if you have any questions.</p>
          </td></tr>
        </table>
      </td></tr>
    </table>
  </body>
</html>"""


def invoice_reminder_email(*, invoice: Invoice, client: Client, organization_name: str, profile=None) -> str:
    profile = profile or object()
    business_name = getattr(profile, "business_name", None) or organization_name
    brand_color = getattr(profile, "brand_color", None)
    if not isinstance(brand_color, str) or not fullmatch(r"#[0-9A-Fa-f]{6}", brand_color):
        brand_color = "#5b8f82"
    days_overdue = (date.today() - invoice.due_date).days
    if days_overdue < 0:
        reminder_message = f"This is a friendly reminder that payment is due on {invoice.due_date.isoformat()}."
    elif days_overdue == 0:
        reminder_message = "This is a friendly reminder that payment is due today."
    else:
        reminder_message = (
            f"Our records show a remaining balance on this invoice, which was due "
            f"{days_overdue} day{'s' if days_overdue != 1 else ''} ago."
        )

    bank_info = getattr(profile, "bank_info", None) or {}
    bank_labels = {
        "bank_name": "Bank",
        "account_name": "Account name",
        "account_number": "Account number",
        "routing_or_swift": "Routing / SWIFT",
    }
    bank_rows = "".join(
        f'<p style="margin:4px 0;color:#53615d;font-size:13px;"><strong>{label}:</strong> {escape(str(bank_info[key]))}</p>'
        for key, label in bank_labels.items()
        if bank_info.get(key)
    )
    footer = getattr(profile, "footer_text", None)

    return f"""\
<!doctype html>
<html lang="en">
  <body style="margin:0;padding:0;background:#eef4f2;color:#26332f;font-family:Arial,Helvetica,sans-serif;">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="padding:28px 12px;background:#eef4f2;">
      <tr><td align="center">
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:600px;background:#ffffff;border:1px solid #dce7e3;border-radius:8px;">
          <tr><td style="padding:28px 32px;border-bottom:3px solid {brand_color};">
            <p style="margin:0;color:{brand_color};font-size:12px;font-weight:700;letter-spacing:1px;text-transform:uppercase;">Payment reminder</p>
            <h1 style="margin:10px 0 0;color:#26332f;font-size:23px;">Invoice {escape(invoice.invoice_number)}</h1>
          </td></tr>
          <tr><td style="padding:26px 32px;">
            <p style="margin:0 0 14px;color:#34413c;font-size:15px;">Hello {escape(client.name)},</p>
            <p style="margin:0 0 20px;color:#53615d;font-size:14px;line-height:1.7;">{escape(reminder_message)}</p>
            <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#f4f8f6;border:1px solid #e3ece8;">
              <tr><td style="padding:13px;color:#53615d;font-size:13px;">Invoice number</td><td align="right" style="padding:13px;color:#26332f;font-size:13px;font-weight:700;">{escape(invoice.invoice_number)}</td></tr>
              <tr><td style="padding:13px;border-top:1px solid #e3ece8;color:#53615d;font-size:13px;">Due date</td><td align="right" style="padding:13px;border-top:1px solid #e3ece8;color:#26332f;font-size:13px;">{invoice.due_date.isoformat()}</td></tr>
              <tr><td style="padding:13px;border-top:1px solid #e3ece8;color:#53615d;font-size:13px;">Remaining balance</td><td align="right" style="padding:13px;border-top:1px solid #e3ece8;color:{brand_color};font-size:16px;font-weight:700;">{escape(invoice.currency)} {invoice.balance_due:,.2f}</td></tr>
            </table>
            {bank_rows}
            <p style="margin:20px 0 0;color:#53615d;font-size:14px;line-height:1.7;">The invoice PDF is attached for your reference. If you have already made this payment, please disregard this reminder. If you have questions, reply to this email and we’ll be happy to help.</p>
            {f'<p style="margin:16px 0 0;color:#53615d;font-size:13px;line-height:1.6;">{escape(footer)}</p>' if footer else ''}
            <p style="margin:20px 0 0;color:#34413c;font-size:14px;">Kind regards,<br><strong>{escape(business_name)}</strong></p>
          </td></tr>
        </table>
      </td></tr>
    </table>
  </body>
</html>"""
