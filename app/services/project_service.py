from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import NotFoundError, ValidationAppError
from app.models.project import Project
from app.repositories.log_repository import LogRepository
from app.repositories.project_repository import ProjectRepository
from app.schemas.project import ProjectCreate, ProjectUpdate


class ProjectService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = ProjectRepository(db)
        self.logs = LogRepository(db)

    async def create(self, *, organization_id: UUID, payload: ProjectCreate, actor_user_id: UUID) -> Project:
        if not await self.repo.client_exists(organization_id=organization_id, client_id=payload.client_id):
            raise ValidationAppError("client_id does not refer to a client in this organization.", error_code="INVALID_CLIENT")

        project = await self.repo.create(organization_id=organization_id, **payload.model_dump())
        await self.logs.record_activity(
            organization_id=organization_id, user_id=actor_user_id, action="project.created",
            entity_type="project", entity_id=project.id,
        )
        await self.db.commit()
        return project

    async def get(self, *, organization_id: UUID, project_id: UUID) -> Project:
        project = await self.repo.get_by_id(organization_id=organization_id, project_id=project_id)
        if not project:
            raise NotFoundError("Project not found.", error_code="PROJECT_NOT_FOUND")
        return project

    async def list(
        self,
        *,
        organization_id: UUID,
        page: int,
        page_size: int,
        client_id: UUID | None,
        status: str | None,
        search: str | None,
    ) -> tuple[list[Project], int]:
        page = max(page, 1)
        page_size = min(max(page_size, 1), settings.max_page_size)
        return await self.repo.list(
            organization_id=organization_id,
            page=page,
            page_size=page_size,
            client_id=client_id,
            status=status,
            search=search,
        )

    async def update(
        self, *, organization_id: UUID, project_id: UUID, payload: ProjectUpdate, actor_user_id: UUID
    ) -> Project:
        project = await self.get(organization_id=organization_id, project_id=project_id)
        project = await self.repo.update(project, **payload.model_dump(exclude_unset=True))
        await self.logs.record_activity(
            organization_id=organization_id, user_id=actor_user_id, action="project.updated",
            entity_type="project", entity_id=project.id,
            metadata={"fields": list(payload.model_dump(exclude_unset=True).keys())},
        )
        await self.db.commit()
        return project

    async def delete(self, *, organization_id: UUID, project_id: UUID, actor_user_id: UUID) -> None:
        project = await self.get(organization_id=organization_id, project_id=project_id)
        await self.repo.soft_delete(project)
        await self.logs.record_audit(
            organization_id=organization_id, user_id=actor_user_id, action="project.deleted",
            entity_type="project", entity_id=project_id,
        )
        await self.db.commit()
