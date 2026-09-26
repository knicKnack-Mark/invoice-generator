from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import NotFoundError, ValidationAppError
from app.models.expense import Expense, ExpenseStatus, VALID_STATUS_TRANSITIONS
from app.repositories.expense_repository import ExpenseRepository
from app.repositories.log_repository import LogRepository
from app.schemas.expense import ExpenseCreate, ExpenseUpdate, UnbilledExpenseItem, UnbilledExpensesSummary


class ExpenseService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = ExpenseRepository(db)
        self.logs = LogRepository(db)

    async def _validate_client_and_project(
        self, *, organization_id: UUID, client_id: UUID, project_id: UUID | None
    ) -> None:
        if not await self.repo.client_exists(organization_id=organization_id, client_id=client_id):
            raise ValidationAppError("client_id does not refer to a client in this organization.", error_code="INVALID_CLIENT")
        if project_id and not await self.repo.project_belongs_to_client(
            organization_id=organization_id, project_id=project_id, client_id=client_id
        ):
            raise ValidationAppError(
                "project_id does not belong to the given client in this organization.", error_code="INVALID_PROJECT"
            )

    async def create(self, *, organization_id: UUID, payload: ExpenseCreate, actor_user_id: UUID) -> Expense:
        await self._validate_client_and_project(
            organization_id=organization_id, client_id=payload.client_id, project_id=payload.project_id
        )
        expense = await self.repo.create(organization_id=organization_id, **payload.model_dump())
        await self.logs.record_activity(
            organization_id=organization_id, user_id=actor_user_id, action="expense.created",
            entity_type="expense", entity_id=expense.id,
        )
        await self.db.commit()
        return expense

    async def duplicate(self, *, organization_id: UUID, expense_id: UUID, actor_user_id: UUID) -> Expense:
        original = await self.get(organization_id=organization_id, expense_id=expense_id)
        copy_fields = dict(
            client_id=original.client_id,
            project_id=original.project_id,
            category_id=original.category_id,
            vendor=original.vendor,
            description=original.description,
            amount=original.amount,
            currency=original.currency,
            tax=original.tax,
            payment_method=original.payment_method,
            expense_date=original.expense_date,
            billable=original.billable,
            reimbursable=original.reimbursable,
            notes=original.notes,
        )
        duplicate = await self.repo.create(organization_id=organization_id, **copy_fields)
        await self.logs.record_activity(
            organization_id=organization_id, user_id=actor_user_id, action="expense.duplicated",
            entity_type="expense", entity_id=duplicate.id, metadata={"duplicated_from": str(expense_id)},
        )
        await self.db.commit()
        return duplicate

    async def get(self, *, organization_id: UUID, expense_id: UUID) -> Expense:
        expense = await self.repo.get_by_id(organization_id=organization_id, expense_id=expense_id)
        if not expense:
            raise NotFoundError("Expense not found.", error_code="EXPENSE_NOT_FOUND")
        return expense

    async def list(self, *, organization_id: UUID, page: int, page_size: int, **filters) -> tuple[list[Expense], int]:
        page = max(page, 1)
        page_size = min(max(page_size, 1), settings.max_page_size)
        return await self.repo.list(organization_id=organization_id, page=page, page_size=page_size, **filters)

    async def update(
        self, *, organization_id: UUID, expense_id: UUID, payload: ExpenseUpdate, actor_user_id: UUID
    ) -> Expense:
        expense = await self.get(organization_id=organization_id, expense_id=expense_id)
        if expense.status in (ExpenseStatus.billed, ExpenseStatus.paid):
            raise ValidationAppError(
                "This expense is already billed/paid and can no longer be edited.", error_code="EXPENSE_LOCKED"
            )

        update_data = payload.model_dump(exclude_unset=True)
        if "project_id" in update_data and update_data["project_id"] is not None:
            client_id = update_data.get("client_id", expense.client_id)
            if not await self.repo.project_belongs_to_client(
                organization_id=organization_id, project_id=update_data["project_id"], client_id=client_id
            ):
                raise ValidationAppError(
                    "project_id does not belong to this expense's client.", error_code="INVALID_PROJECT"
                )

        expense = await self.repo.update(expense, **update_data)
        await self.logs.record_activity(
            organization_id=organization_id, user_id=actor_user_id, action="expense.updated",
            entity_type="expense", entity_id=expense.id, metadata={"fields": list(update_data.keys())},
        )
        await self.db.commit()
        return expense

    async def update_status(
        self, *, organization_id: UUID, expense_id: UUID, new_status: str, actor_user_id: UUID
    ) -> Expense:
        expense = await self.get(organization_id=organization_id, expense_id=expense_id)
        target = ExpenseStatus(new_status)
        allowed = VALID_STATUS_TRANSITIONS.get(expense.status, set())
        if target not in allowed:
            raise ValidationAppError(
                f"Cannot move expense from '{expense.status.value}' to '{target.value}'.",
                error_code="INVALID_STATUS_TRANSITION",
            )
        expense = await self.repo.set_status(expense, target)
        await self.logs.record_activity(
            organization_id=organization_id, user_id=actor_user_id, action="expense.status_changed",
            entity_type="expense", entity_id=expense.id,
            metadata={"from": expense.status.value, "to": target.value},
        )
        await self.db.commit()
        return expense

    async def delete(self, *, organization_id: UUID, expense_id: UUID, actor_user_id: UUID) -> None:
        expense = await self.get(organization_id=organization_id, expense_id=expense_id)
        if expense.status in (ExpenseStatus.billed, ExpenseStatus.paid):
            raise ValidationAppError(
                "This expense is already billed/paid and cannot be deleted.", error_code="EXPENSE_LOCKED"
            )
        await self.repo.soft_delete(expense)
        await self.logs.record_audit(
            organization_id=organization_id, user_id=actor_user_id, action="expense.deleted",
            entity_type="expense", entity_id=expense_id,
        )
        await self.db.commit()

    async def unbilled_summary(self, *, organization_id: UUID, client_id: UUID) -> UnbilledExpensesSummary:
        expenses = await self.repo.list_unbilled(organization_id=organization_id, client_id=client_id)
        currency = expenses[0].currency if expenses else "USD"
        total = sum((e.amount for e in expenses if e.currency == currency), Decimal("0"))
        items = [
            UnbilledExpenseItem(
                id=e.id, vendor=e.vendor, description=e.description,
                amount=e.amount, currency=e.currency, expense_date=e.expense_date,
            )
            for e in expenses
        ]
        return UnbilledExpensesSummary(total=total, currency=currency, count=len(items), items=items)
