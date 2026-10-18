import os

# These must be set before any app code is imported: settings are read once at import.
os.environ["RATE_LIMIT_ENABLED"] = "false"   # the tests send far more than 60 requests/minute
os.environ["ENVIRONMENT"] = "development"    # secure cookies would never be sent back over http://
os.environ["STORAGE_LOCAL_DIR"] = "./.test_uploads"
os.environ.setdefault("JWT_SECRET", "test-secret")
if os.environ.get("TEST_DATABASE_URL"):
    os.environ["DATABASE_URL"] = os.environ["TEST_DATABASE_URL"]
else:
    os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost/test")

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac