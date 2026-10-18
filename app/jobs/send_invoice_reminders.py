import asyncio
import logging
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.integrations.email import get_email_backend
from app.integrations.email_templates import invoice_reminder_email
from app.integrations.pdf import render_invoice_pdf
from app.integrations.storage import get_storage_backend
from app.models import Client, Invoice, InvoiceReminder, InvoiceStatus, Organization, OrganizationSettings
from app.models.base import AsyncSessionLocal, engine

logger = logging.getLogger(__name__)


async def run_reminders(run_date: date | None = None) -> None:
    run_date = run_date or date.today()
    offsets = settings.invoice_reminder_day_offsets
    if not offsets:
        logger.info("Invoice reminders are disabled because no reminder offsets are configured.")
        return

    due_dates = {run_date - timedelta(days=offset): offset for offset in offsets}
    statuses = [InvoiceStatus.sent, InvoiceStatus.viewed, InvoiceStatus.partially_paid]
    failures = 0

    async with AsyncSessionLocal() as db:
        invoices = (
            await db.execute(
                select(Invoice)
                .where(
                    Invoice.due_date.in_(due_dates),
                    Invoice.status.in_(statuses),
                    Invoice.amount_paid < Invoice.total,
                    Invoice.deleted_at.is_(None),
                )
                .options(
                    selectinload(Invoice.items),
                    selectinload(Invoice.expenses),
                    selectinload(Invoice.time_entries),
                )
            )
        ).scalars().all()

        email_backend = get_email_backend()
        storage_backend = get_storage_backend()
        for invoice in invoices:
            offset = due_dates[invoice.due_date]
            reminder_exists = await db.scalar(
                select(InvoiceReminder.id).where(
                    InvoiceReminder.invoice_id == invoice.id,
                    InvoiceReminder.days_from_due == offset,
                )
            )
            if reminder_exists:
                continue

            client = await db.get(Client, invoice.client_id)
            if (
                client is None
                or client.deleted_at is not None
                or client.organization_id != invoice.organization_id
                or not client.email
            ):
                logger.warning("Skipping invoice reminder for %s: client is deleted or has no valid email.", invoice.id)
                continue

            try:
                organization = await db.get(Organization, invoice.organization_id)
                profile = await db.scalar(
                    select(OrganizationSettings).where(
                        OrganizationSettings.organization_id == invoice.organization_id
                    )
                )
                organization_name = organization.name if organization else "Your service provider"
                html_body = invoice_reminder_email(
                    invoice=invoice,
                    client=client,
                    organization_name=organization_name,
                    profile=profile,
                )
                logo_bytes = None
                if profile and profile.logo_key:
                    logo_bytes = await storage_backend.read(key=profile.logo_key)
                pdf_bytes = render_invoice_pdf(
                    invoice=invoice,
                    client_name=client.name,
                    organization_name=organization_name,
                    profile=profile,
                    logo_bytes=logo_bytes,
                )

                await email_backend.send(
                    to=client.email,
                    subject=f"Payment reminder: invoice {invoice.invoice_number}",
                    html_body=html_body,
                    from_name=getattr(profile, "business_name", None) or organization_name,
                    attachments=[(f"{invoice.invoice_number}.pdf", pdf_bytes, "application/pdf")],
                )
                db.add(
                    InvoiceReminder(
                        invoice_id=invoice.id,
                        days_from_due=offset,
                        scheduled_date=run_date,
                        sent_at=datetime.now(timezone.utc),
                    )
                )
                await db.commit()
                logger.info("Sent invoice reminder for %s to %s.", invoice.id, client.email)
            except Exception:
                await db.rollback()
                failures += 1
                logger.exception("Failed to send invoice reminder for %s.", invoice.id)

    if failures:
        raise RuntimeError(f"{failures} invoice reminder(s) failed to send.")


async def main() -> None:
    try:
        await run_reminders()
    finally:
        await engine.dispose()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    asyncio.run(main())
