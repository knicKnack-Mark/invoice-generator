from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.client import Client
from app.models.project import BillingType, Project, ProjectStatus


class ProjectRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def client_exists(self, *, organization_id: UUID, client_id: UUID) -> bool:
        result = await self.db.execute(
            select(Client.id).where(
                Client.id == client_id,
                Client.organization_id == organization_id,
                Client.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none() is not None

    async def create(self, *, organization_id: UUID, **fields) -> Project:
        project = Project(organization_id=organization_id, **fields)
        self.db.add(project)
        await self.db.flush()
        return project

    async def get_by_id(self, *, organization_id: UUID, project_id: UUID) -> Project | None:
        result = await self.db.execute(
            select(Project).where(
                Project.id == project_id,
                Project.organization_id == organization_id,
                Project.deleted_at.is_(None),
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
        status: str | None = None,
        search: str | None = None,
    ) -> tuple[list[Project], int]:
        conditions = [Project.organization_id == organization_id, Project.deleted_at.is_(None)]
        if client_id:
            conditions.append(Project.client_id == client_id)
        if status:
            conditions.append(Project.status == ProjectStatus(status))
        if search:
            conditions.append(Project.name.ilike(f"%{search}%"))

        count_result = await self.db.execute(
            select(func.count()).select_from(Project).where(*conditions)
        )
        total = count_result.scalar_one()

        result = await self.db.execute(
            select(Project)
            .where(*conditions)
            .order_by(Project.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(result.scalars().all()), total

    async def update(self, project: Project, **fields) -> Project:
        for key, value in fields.items():
            if value is None:
                continue
            if key == "status":
                value = ProjectStatus(value)
            elif key == "billing_type":
                value = BillingType(value)
            setattr(project, key, value)
        await self.db.flush()
        return project

    async def soft_delete(self, project: Project) -> None:
        from datetime import datetime, timezone

        project.deleted_at = datetime.now(timezone.utc)
        await self.db.flush()
