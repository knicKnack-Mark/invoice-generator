import os

from dotenv import dotenv_values

# These must be set before any app code is imported: settings are read once at import.
os.environ["RATE_LIMIT_ENABLED"] = "false"   # the tests send far more than 60 requests/minute
os.environ["ENVIRONMENT"] = "development"    # secure cookies would never be sent back over http://
os.environ["STORAGE_LOCAL_DIR"] = "./.test_uploads"

test_database_url = os.environ.get("TEST_DATABASE_URL") or dotenv_values(".env").get("TEST_DATABASE_URL")
if test_database_url:
    os.environ["DATABASE_URL"] = test_database_url
elif not os.path.exists(".env"):
    # No .env found (run pytest from the backend/ folder so it's picked up).
    os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost/test")
    os.environ.setdefault("JWT_SECRET", "test-secret")

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac