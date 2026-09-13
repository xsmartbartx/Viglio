from __future__ import annotations

import uuid

import pytest_asyncio

from vigilo_api.deps import require_account
from vigilo_api.main import app
from vigilo_identity.repository import get_or_create_account
from vigilo_persistence import session_scope


@pytest_asyncio.fixture
async def account():
    async with session_scope() as session:
        acc = await get_or_create_account(
            session, email="owner@example.com", clerk_user_id="user_test"
        )
    app.dependency_overrides[require_account] = lambda: acc
    yield acc
    app.dependency_overrides.pop(require_account, None)


async def test_create_target_returns_201(client, account):
    response = await client.post("/v1/targets", json={"origin": "https://example.com"})

    assert response.status_code == 201
    body = response.json()
    assert body["origin"] == "https://example.com"
    assert body["verification_status"] == "passive"


async def test_create_target_rejects_a_malformed_origin(client, account):
    response = await client.post("/v1/targets", json={"origin": "not-a-url"})
    assert response.status_code == 422


async def test_get_target_returns_404_for_someone_elses_target(client, account):
    create_response = await client.post("/v1/targets", json={"origin": "https://example.com"})
    target_id = create_response.json()["target_id"]

    async with session_scope() as session:
        other = await get_or_create_account(
            session, email="other@example.com", clerk_user_id="user_other"
        )
    app.dependency_overrides[require_account] = lambda: other

    response = await client.get(f"/v1/targets/{target_id}")
    assert response.status_code == 404


async def test_initiate_and_check_verification_flow(client, account):
    create_response = await client.post("/v1/targets", json={"origin": "https://example.com"})
    target_id = create_response.json()["target_id"]

    initiate_response = await client.post(
        f"/v1/targets/{target_id}/verification", json={"method": "dns_txt"}
    )
    assert initiate_response.status_code == 201
    body = initiate_response.json()
    assert body["method"] == "dns_txt"
    assert body["nonce"]
    assert "vigilo-site-verification" in body["instructions"]

    proof_id = body["proof_id"]
    check_response = await client.post(f"/v1/targets/{target_id}/verification/{proof_id}/check")

    assert check_response.status_code == 202
    assert check_response.json()["status"] == "checking"


async def test_verification_check_for_an_unknown_proof_returns_404(client, account):
    create_response = await client.post("/v1/targets", json={"origin": "https://example.com"})
    target_id = create_response.json()["target_id"]

    response = await client.post(f"/v1/targets/{target_id}/verification/{uuid.uuid4()}/check")
    assert response.status_code == 404


async def test_target_endpoints_require_authentication(client):
    response = await client.post("/v1/targets", json={"origin": "https://example.com"})
    assert response.status_code == 401
