# import
from app.repositories.expense_repository import ExpenseCategoryRepository, ExpenseRepository

# in __init__
self.categories = ExpenseCategoryRepository(db)

# new method
async def _validate_category(self, *, organization_id: UUID, category_id: UUID | None) -> None:
    if category_id and not await self.categories.get_by_id(organization_id=organization_id, category_id=category_id):
        raise ValidationAppError(
            "category_id does not refer to a category in this organization.", error_code="INVALID_CATEGORY"
        )

# in create(), right after _validate_client_and_project(...)
await self._validate_category(organization_id=organization_id, category_id=payload.category_id)

# in update(), right after `update_data = payload.model_dump(exclude_unset=True)`
await self._validate_category(organization_id=organization_id, category_id=update_data.get("category_id"))