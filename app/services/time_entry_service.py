# import
from app.repositories.expense_repository import ExpenseRepository

# in __init__
self.expenses = ExpenseRepository(db)

# in create(), right after the client check
if payload.project_id and not await self.expenses.project_belongs_to_client(
    organization_id=organization_id, project_id=payload.project_id, client_id=payload.client_id
):
    raise ValidationAppError(
        "project_id does not belong to the given client in this organization.", error_code="INVALID_PROJECT"
    )

# in update(), replace the `entry = await self.repo.update(...)` line with
update_data = payload.model_dump(exclude_unset=True)
if update_data.get("project_id") and not await self.expenses.project_belongs_to_client(
    organization_id=organization_id, project_id=update_data["project_id"], client_id=entry.client_id
):
    raise ValidationAppError(
        "project_id does not belong to this entry's client.", error_code="INVALID_PROJECT"
    )
entry = await self.repo.update(entry, **update_data)