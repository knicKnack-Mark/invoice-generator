from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import NotFoundError
from app.models.client import Client
from app.repositories.client_repository import ClientRepository
from app.repositories.log_repository import LogRepository
from app.schemas.client import ClientCreate, ClientUpdate


class ClientService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = ClientRepository(db)
        self.logs = LogRepository(db)

    async def create(self, *, organization_id: UUID, payload: ClientCreate, actor_user_id: UUID) -> Client:
        client = await self.repo.create(organization_id=organization_id, **payload.model_dump())
        await self.logs.record_activity(
            organization_id=organization_id, user_id=actor_user_id, action="client.created",
            entity_type="client", entity_id=client.id,
        )
        await self.db.commit()
        return client

    async def get(self, *, organization_id: UUID, client_id: UUID) -> Client:
        client = await self.repo.get_by_id(organization_id=organization_id, client_id=client_id)
        if not client:
            raise NotFoundError("Client not found.", error_code="CLIENT_NOT_FOUND")
        return client

    async def list(
        self,
        *,
        organization_id: UUID,
        page: int,
        page_size: int,
        search: str | None,
        status: str | None,
    ) -> tuple[list[Client], int]:
        page = max(page, 1)
        page_size = min(max(page_size, 1), settings.max_page_size)
        return await self.repo.list(
            organization_id=organization_id,
            page=page,
            page_size=page_size,
            search=search,
            status=status,
        )

    async def update(
        self, *, organization_id: UUID, client_id: UUID, payload: ClientUpdate, actor_user_id: UUID
    ) -> Client:
        client = await self.get(organization_id=organization_id, client_id=client_id)
        client = await self.repo.update(client, **payload.model_dump(exclude_unset=True))
        await self.logs.record_activity(
            organization_id=organization_id, user_id=actor_user_id, action="client.updated",
            entity_type="client", entity_id=client.id,
            metadata={"fields": list(payload.model_dump(exclude_unset=True).keys())},
        )
        await self.db.commit()
        return client

    async def delete(self, *, organization_id: UUID, client_id: UUID, actor_user_id: UUID) -> None:
        client = await self.get(organization_id=organization_id, client_id=client_id)
        await self.repo.soft_delete(client)
        # Deletions of financial records are audit-worthy, not just activity-worthy.
        await self.logs.record_audit(
            organization_id=organization_id, user_id=actor_user_id, action="client.deleted",
            entity_type="client", entity_id=client_id,
        )
        await self.db.commit()
