from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.base import get_db

router = APIRouter(tags=["health"])


@router.get("/health")
async def health():
    return {"success": True, "data": {"status": "ok"}}


@router.get("/health/db")
async def health_db(db: AsyncSession = Depends(get_db)):
    await db.execute(text("SELECT 1"))
    return {"success": True, "data": {"status": "ok", "database": "connected"}}


@router.get("/ping")
async def ping():
    """Unauthenticated, unrestricted endpoint for the frontend to check that
    it can reach the backend at all (network/CORS sanity check) — separate
    from /health/db, which also proves the database connection works."""
    return {
        "success": True,
        "data": {
            "status": "ok",
            "service": settings.app_name,
            "version": settings.app_version,
            "environment": settings.environment,
            "server_time": datetime.now(timezone.utc).isoformat(),
        },
    }
