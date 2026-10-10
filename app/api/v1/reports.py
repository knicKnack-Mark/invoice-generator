from datetime import date

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_role
from app.models.base import get_db
from app.models.organization import OrganizationMember
from app.schemas.reports import ExpenseReport, OutstandingInvoicesReport, ProfitabilityReport, RevenueReport
from app.services.report_service import ReportService

router = APIRouter(prefix="/reports", tags=["reports"])

READ_ROLES = ("owner", "admin", "manager", "accountant")


def _csv_response(csv_text: str, filename: str) -> StreamingResponse:
    return StreamingResponse(
        iter([csv_text]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/revenue", response_model=RevenueReport)
async def revenue_report(
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    membership: OrganizationMember = Depends(require_role(*READ_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    return await ReportService(db).revenue_report(
        organization_id=membership.organization_id, date_from=date_from, date_to=date_to
    )


@router.get("/expenses", response_model=ExpenseReport)
async def expense_report(
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    membership: OrganizationMember = Depends(require_role(*READ_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    return await ReportService(db).expense_report(
        organization_id=membership.organization_id, date_from=date_from, date_to=date_to
    )


@router.get("/outstanding-invoices", response_model=OutstandingInvoicesReport)
async def outstanding_invoices_report(
    membership: OrganizationMember = Depends(require_role(*READ_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    return await ReportService(db).outstanding_invoices_report(organization_id=membership.organization_id)


@router.get("/profitability", response_model=ProfitabilityReport)
async def profitability_report(
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    membership: OrganizationMember = Depends(require_role(*READ_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    return await ReportService(db).profitability_report(
        organization_id=membership.organization_id, date_from=date_from, date_to=date_to
    )


@router.get("/export/expenses.csv")
async def export_expenses_csv(
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    membership: OrganizationMember = Depends(require_role(*READ_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    csv_text = await ReportService(db).export_expenses_csv(
        organization_id=membership.organization_id, date_from=date_from, date_to=date_to
    )
    return _csv_response(csv_text, "expenses.csv")


@router.get("/export/invoices.csv")
async def export_invoices_csv(
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    membership: OrganizationMember = Depends(require_role(*READ_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    csv_text = await ReportService(db).export_invoices_csv(
        organization_id=membership.organization_id, date_from=date_from, date_to=date_to
    )
    return _csv_response(csv_text, "invoices.csv")


@router.get("/export/payments.csv")
async def export_payments_csv(
    membership: OrganizationMember = Depends(require_role(*READ_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    csv_text = await ReportService(db).export_payments_csv(organization_id=membership.organization_id)
    return _csv_response(csv_text, "payments.csv")