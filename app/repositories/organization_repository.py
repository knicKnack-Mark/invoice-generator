import re
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.organization import Organization, OrganizationMember, OrgRole


class OrganizationRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    @staticmethod
    def slugify(name: str) -> str:
        base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
        return base or "org"

    async def create(self, *, name: str, owner_user_id: UUID) -> Organization:
        slug = self.slugify(name)
        # ensure uniqueness by suffixing if needed
        suffix = 0
        candidate = slug
        while await self._slug_exists(candidate):
            suffix += 1
            candidate = f"{slug}-{suffix}"

        org = Organization(name=name, slug=candidate)
        self.db.add(org)
        await self.db.flush()

        membership = OrganizationMember(
            organization_id=org.id, user_id=owner_user_id, role=OrgRole.owner
        )
        self.db.add(membership)
        await self.db.flush()
        return org

    async def _slug_exists(self, slug: str) -> bool:
        result = await self.db.execute(select(Organization).where(Organization.slug == slug))
        return result.scalar_one_or_none() is not None

    async def get_membership(self, *, organization_id: UUID, user_id: UUID) -> OrganizationMember | None:
        result = await self.db.execute(
            select(OrganizationMember).where(
                OrganizationMember.organization_id == organization_id,
                OrganizationMember.user_id == user_id,
                OrganizationMember.status == "active",
            )
        )
        return result.scalar_one_or_none()

    async def list_for_user(self, user_id: UUID) -> list[tuple[Organization, OrganizationMember]]:
        result = await self.db.execute(
            select(Organization, OrganizationMember)
            .join(OrganizationMember, OrganizationMember.organization_id == Organization.id)
            .where(OrganizationMember.user_id == user_id, OrganizationMember.status == "active")
        )
        return list(result.all())
