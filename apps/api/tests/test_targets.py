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


async def test_list_targets_returns_only_the_callers_targets(client, account):
    # Free plan's targets_limit is 1 — one target for `account` is enough
    # to prove isolation without tripping the quota this test isn't about.
    create_response = await client.post("/v1/targets", json={"origin": "https://example.com"})
    assert create_response.status_code == 201

    async with session_scope() as session:
        other = await get_or_create_account(
            session, email="other-list@example.com", clerk_user_id="user_other_list"
        )
    app.dependency_overrides[require_account] = lambda: other
    other_response = await client.post(
        "/v1/targets", json={"origin": "https://not-mine.example.com"}
    )
    assert other_response.status_code == 201

    app.dependency_overrides[require_account] = lambda: account
    response = await client.get("/v1/targets")

    assert response.status_code == 200
    assert {target["origin"] for target in response.json()} == {"https://example.com"}


async def test_list_targets_for_an_account_with_none_returns_an_empty_list(client, account):
    response = await client.get("/v1/targets")
    assert response.status_code == 200
    assert response.json() == []


async def test_list_targets_requires_authentication(client):
    response = await client.get("/v1/targets")
    assert response.status_code == 401


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


async def test_create_target_beyond_the_free_plan_limit_is_denied(client, account):
    """Free plan's targets_limit is 1 (packages/billing/plans.py) — a second,
    genuinely new origin is denied; the account's own existing target isn't
    counted twice against it."""
    first = await client.post("/v1/targets", json={"origin": "https://example.com"})
    assert first.status_code == 201

    second = await client.post("/v1/targets", json={"origin": "https://second.example.com"})

    assert second.status_code == 429
    assert second.json()["code"] == "QUOTA_EXCEEDED"


async def test_creating_a_target_for_an_already_tracked_origin_never_counts_against_quota(
    client, account
):
    first = await client.post("/v1/targets", json={"origin": "https://example.com"})
    assert first.status_code == 201

    repeat = await client.post("/v1/targets", json={"origin": "https://example.com"})

    assert repeat.status_code == 201
