from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.client import Client
from app.models.expense import Expense, ExpenseCategory, ExpenseStatus
from app.models.project import Project


class ExpenseCategoryRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list(self, *, organization_id: UUID) -> list[ExpenseCategory]:
        result = await self.db.execute(
            select(ExpenseCategory)
            .where(ExpenseCategory.organization_id == organization_id)
            .order_by(ExpenseCategory.name)
        )
        return list(result.scalars().all())

    async def create(self, *, organization_id: UUID, name: str) -> ExpenseCategory:
        category = ExpenseCategory(organization_id=organization_id, name=name)
        self.db.add(category)
        await self.db.flush()
        return category

    async def get_by_id(self, *, organization_id: UUID, category_id: UUID) -> ExpenseCategory | None:
        result = await self.db.execute(
            select(ExpenseCategory).where(
                ExpenseCategory.id == category_id, ExpenseCategory.organization_id == organization_id
            )
        )
        return result.scalar_one_or_none()

    async def seed_defaults(self, *, organization_id: UUID) -> None:
        """Called once at org creation so a new org isn't empty of categories."""
        defaults = ["Software", "Advertising", "Shipping", "Supplies", "Transportation", "Other"]
        for name in defaults:
            self.db.add(ExpenseCategory(organization_id=organization_id, name=name, is_default=True))
        await self.db.flush()


class ExpenseRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def client_exists(self, *, organization_id: UUID, client_id: UUID) -> bool:
        result = await self.db.execute(
            select(Client.id).where(
                Client.id == client_id, Client.organization_id == organization_id, Client.deleted_at.is_(None)
            )
        )
        return result.scalar_one_or_none() is not None

    async def project_belongs_to_client(self, *, organization_id: UUID, project_id: UUID, client_id: UUID) -> bool:
        result = await self.db.execute(
            select(Project.id).where(
                Project.id == project_id,
                Project.organization_id == organization_id,
                Project.client_id == client_id,
                Project.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none() is not None

    async def create(self, *, organization_id: UUID, **fields) -> Expense:
        expense = Expense(organization_id=organization_id, **fields)
        self.db.add(expense)
        await self.db.flush()
        return expense

    async def get_by_id(self, *, organization_id: UUID, expense_id: UUID) -> Expense | None:
        result = await self.db.execute(
            select(Expense).where(
                Expense.id == expense_id,
                Expense.organization_id == organization_id,
                Expense.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def list(
        self,
        *,
        organization_id: UUID,
        page: int,
        page_size: int,
        client_id: UUID | None = None,
        project_id: UUID | None = None,
        category_id: UUID | None = None,
        status: str | None = None,
        billable: bool | None = None,
        reimbursable: bool | None = None,
        currency: str | None = None,
        date_from=None,
        date_to=None,
        search: str | None = None,
    ) -> tuple[list[Expense], int]:
        conditions = [Expense.organization_id == organization_id, Expense.deleted_at.is_(None)]
        if client_id:
            conditions.append(Expense.client_id == client_id)
        if project_id:
            conditions.append(Expense.project_id == project_id)
        if category_id:
            conditions.append(Expense.category_id == category_id)
        if status:
            conditions.append(Expense.status == ExpenseStatus(status))
        if billable is not None:
            conditions.append(Expense.billable == billable)
        if reimbursable is not None:
            conditions.append(Expense.reimbursable == reimbursable)
        if currency:
            conditions.append(Expense.currency == currency.upper())
        if date_from:
            conditions.append(Expense.expense_date >= date_from)
        if date_to:
            conditions.append(Expense.expense_date <= date_to)
        if search:
            like_term = f"%{search}%"
            conditions.append((Expense.vendor.ilike(like_term)) | (Expense.description.ilike(like_term)))

        count_result = await self.db.execute(select(func.count()).select_from(Expense).where(*conditions))
        total = count_result.scalar_one()

        result = await self.db.execute(
            select(Expense)
            .where(*conditions)
            .order_by(Expense.expense_date.desc(), Expense.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(result.scalars().all()), total

    async def list_unbilled(self, *, organization_id: UUID, client_id: UUID) -> list[Expense]:
        result = await self.db.execute(
            select(Expense).where(
                Expense.organization_id == organization_id,
                Expense.client_id == client_id,
                Expense.billable.is_(True),
                Expense.invoiced_at.is_(None),
                Expense.deleted_at.is_(None),
                Expense.status.in_([ExpenseStatus.approved, ExpenseStatus.pending, ExpenseStatus.draft]),
            ).order_by(Expense.expense_date.asc())
        )
        return list(result.scalars().all())

    async def update(self, expense: Expense, **fields) -> Expense:
        for key, value in fields.items():
            if value is not None:
                setattr(expense, key, value)
        await self.db.flush()
        return expense

    async def set_status(self, expense: Expense, status: ExpenseStatus) -> Expense:
        expense.status = status
        await self.db.flush()
        return expense

    async def soft_delete(self, expense: Expense) -> None:
        expense.deleted_at = datetime.now(timezone.utc)
        await self.db.flush()
