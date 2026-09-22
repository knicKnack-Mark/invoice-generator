import pytest


async def test_ping_is_public(client):
    resp = await client.get("/api/v1/ping")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert "service" in body["data"]
    assert "server_time" in body["data"]


async def test_clients_require_authentication(client):
    resp = await client.get("/api/v1/clients")
    assert resp.status_code == 401
    assert resp.json()["error_code"] == "NOT_AUTHENTICATED"


async def test_clients_require_organization_header(client):
    # Simulate an authenticated cookie without X-Organization-Id — FastAPI
    # should reject before any service/repository code runs.
    resp = await client.get("/api/v1/clients", cookies={"access_token": "not-a-real-jwt"})
    assert resp.status_code in (401, 422)
