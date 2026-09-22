from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.client import Client, ClientStatus


class ClientRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, *, organization_id: UUID, **fields) -> Client:
        client = Client(organization_id=organization_id, **fields)
        self.db.add(client)
        await self.db.flush()
        return client

    async def get_by_id(self, *, organization_id: UUID, client_id: UUID) -> Client | None:
        # organization_id is always part of the WHERE clause — a client from
        # another org simply does not match this query, regardless of what
        # client_id is supplied.
        result = await self.db.execute(
            select(Client).where(
                Client.id == client_id,
                Client.organization_id == organization_id,
                Client.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def list(
        self,
        *,
        organization_id: UUID,
        page: int,
        page_size: int,
        search: str | None = None,
        status: str | None = None,
    ) -> tuple[list[Client], int]:
        conditions = [Client.organization_id == organization_id, Client.deleted_at.is_(None)]

        if status:
            conditions.append(Client.status == ClientStatus(status))
        if search:
            # Bound parameter via SQLAlchemy's ilike — the search term is
            # never concatenated into raw SQL, so it can't inject.
            like_term = f"%{search}%"
            conditions.append(
                (Client.name.ilike(like_term))
                | (Client.company_name.ilike(like_term))
                | (Client.email.ilike(like_term))
            )

        count_result = await self.db.execute(
            select(func.count()).select_from(Client).where(*conditions)
        )
        total = count_result.scalar_one()

        result = await self.db.execute(
            select(Client)
            .where(*conditions)
            .order_by(Client.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(result.scalars().all()), total

    async def update(self, client: Client, **fields) -> Client:
        for key, value in fields.items():
            if value is None:
                continue
            if key == "status":
                value = ClientStatus(value)
            setattr(client, key, value)
        await self.db.flush()
        return client

    async def soft_delete(self, client: Client) -> None:
        from datetime import datetime, timezone

        client.deleted_at = datetime.now(timezone.utc)
        await self.db.flush()
