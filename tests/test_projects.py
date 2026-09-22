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
    return resp.json()["organizations"][0]["id"]


async def test_project_requires_client_in_same_org(client):
    if not await _db_reachable():
        pytest.skip("No reachable test database configured.")

    org_a_id = await _register(client, "proj-a@example.com", "Org A")
    org_b_id = await _register(client, "proj-b@example.com", "Org B")

    client_resp = await client.post(
        "/api/v1/clients", json={"name": "Org A Client"}, headers={"X-Organization-Id": org_a_id}
    )
    org_a_client_id = client_resp.json()["id"]

    # Attempting to create a project in Org B that points at Org A's client
    # must fail — this is the cross-tenant-attachment guard.
    cross_resp = await client.post(
        "/api/v1/projects",
        json={"name": "Sneaky Project", "client_id": org_a_client_id, "billing_type": "fixed", "fixed_rate": "500"},
        headers={"X-Organization-Id": org_b_id},
    )
    assert cross_resp.status_code == 422
    assert cross_resp.json()["error_code"] == "INVALID_CLIENT"

    # Same request against the correct org succeeds.
    ok_resp = await client.post(
        "/api/v1/projects",
        json={"name": "Legit Project", "client_id": org_a_client_id, "billing_type": "fixed", "fixed_rate": "500"},
        headers={"X-Organization-Id": org_a_id},
    )
    assert ok_resp.status_code == 201


async def test_project_billing_type_requires_matching_rate(client):
    if not await _db_reachable():
        pytest.skip("No reachable test database configured.")

    org_id = await _register(client, "proj-rate@example.com", "Org Rate")
    client_resp = await client.post(
        "/api/v1/clients", json={"name": "Rate Client"}, headers={"X-Organization-Id": org_id}
    )
    client_id = client_resp.json()["id"]

    # hourly billing without hourly_rate must be rejected by request validation.
    resp = await client.post(
        "/api/v1/projects",
        json={"name": "No Rate", "client_id": client_id, "billing_type": "hourly"},
        headers={"X-Organization-Id": org_id},
    )
    assert resp.status_code == 422
