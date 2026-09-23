import uuid
from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from uuid import uuid4
from sqlalchemy.pool import NullPool
from app.core.config import settings

POOLER_CONNECT_ARGS = {
    "statement_cache_size": 0,
    "prepared_statement_cache_size": 0,
    "prepared_statement_name_func": lambda: f"__asyncpg_{uuid4()}__",
    "ssl": "require",
}

engine = create_async_engine(
    settings.database_url,
    poolclass=NullPool,
    connect_args=POOLER_CONNECT_ARGS,
)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class UUIDPKMixin:
    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session
