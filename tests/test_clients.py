"""
These tests exercise the full stack against a real Postgres database (a
disposable Supabase branch/project or local test DB works). Point
DATABASE_URL at that database and run `alembic upgrade head` before running
these — they are skipped automatically if the DB is unreachable so they
never block a plain `pytest` run against the unit-level tests.
"""
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import settings


async def _db_reachable() -> bool:
    try:
        engine = create_async_engine(settings.database_url)
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        await engine.dispose()
        return True
    except Exception:
        return False


async def _register(client, email: str, org_name: str):
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "correct-horse-battery-staple",
            "full_name": "Test User",
            "organization_name": org_name,
        },
    )
    assert resp.status_code == 200, resp.text
    return resp


async def test_client_crud_happy_path(client):
    if not await _db_reachable():
        pytest.skip("No reachable test database configured.")

    resp = await _register(client, "va+clients@example.com", "VA Co")
    org_id = resp.json()["organizations"][0]["id"]
    headers = {"X-Organization-Id": org_id}

    create_resp = await client.post(
        "/api/v1/clients",
        json={"name": "Acme Corp", "email": "billing@acme.test", "currency": "usd"},
        headers=headers,
    )
    assert create_resp.status_code == 201
    body = create_resp.json()
    assert body["currency"] == "USD"  # normalized uppercase
    client_id = body["id"]

    get_resp = await client.get(f"/api/v1/clients/{client_id}", headers=headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["name"] == "Acme Corp"

    update_resp = await client.patch(
        f"/api/v1/clients/{client_id}", json={"status": "inactive"}, headers=headers
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["status"] == "inactive"

    delete_resp = await client.delete(f"/api/v1/clients/{client_id}", headers=headers)
    assert delete_resp.status_code == 200

    # Soft-deleted client must not be retrievable anymore.
    after_delete = await client.get(f"/api/v1/clients/{client_id}", headers=headers)
    assert after_delete.status_code == 404


async def test_tenant_isolation_on_clients(client):
    if not await _db_reachable():
        pytest.skip("No reachable test database configured.")

    resp_a = await _register(client, "orga@example.com", "Org A")
    org_a_id = resp_a.json()["organizations"][0]["id"]

    resp_b = await _register(client, "orgb@example.com", "Org B")
    org_b_id = resp_b.json()["organizations"][0]["id"]

    create_resp = await client.post(
        "/api/v1/clients",
        json={"name": "Org A's Client"},
        headers={"X-Organization-Id": org_a_id},
    )
    client_id = create_resp.json()["id"]

    # A member of Org B must not be able to read Org A's client, even
    # knowing its exact ID.
    cross_tenant_resp = await client.get(
        f"/api/v1/clients/{client_id}", headers={"X-Organization-Id": org_b_id}
    )
    assert cross_tenant_resp.status_code in (403, 404)
