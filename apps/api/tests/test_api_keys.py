from __future__ import annotations

import uuid

import pytest_asyncio

from vigilo_api.deps import require_account
from vigilo_api.main import app
from vigilo_identity.repository import (
    get_account_by_id,
    get_or_create_account,
    upsert_subscription,
)
from vigilo_persistence import session_scope


async def _upgrade_to_builder(account_id, email: str):
    async with session_scope() as session:
        await upsert_subscription(
            session,
            account_id=account_id,
            plan_id="builder",
            status="active",
            provider="paddle",
            provider_subscription_id=f"sub_{email}",
            current_period_end=None,
        )
        return await get_account_by_id(session, account_id)


@pytest_asyncio.fixture
async def builder_account():
    async with session_scope() as session:
        acc = await get_or_create_account(
            session, email="apikey-owner@example.com", clerk_user_id="user_apikey"
        )
    acc = await _upgrade_to_builder(acc.id, acc.email)
    app.dependency_overrides[require_account] = lambda: acc
    yield acc
    app.dependency_overrides.pop(require_account, None)


@pytest_asyncio.fixture
async def free_account():
    async with session_scope() as session:
        acc = await get_or_create_account(
            session, email="apikey-free@example.com", clerk_user_id="user_apikey_free"
        )
    app.dependency_overrides[require_account] = lambda: acc
    yield acc
    app.dependency_overrides.pop(require_account, None)


async def test_create_api_key_on_the_free_plan_is_denied(client, free_account):
    response = await client.post(
        "/v1/me/api-keys", json={"name": "test key", "scopes": ["scan:read"]}
    )
    assert response.status_code == 429
    assert response.json()["code"] == "QUOTA_EXCEEDED"


async def test_create_api_key_returns_the_plaintext_once(client, builder_account):
    response = await client.post(
        "/v1/me/api-keys", json={"name": "CI pipeline", "scopes": ["scan:run", "scan:read"]}
    )

    assert response.status_code == 201
    body = response.json()
    assert body["api_key"].startswith("vglo_")
    assert body["prefix"] == body["api_key"][:12]
    assert body["scopes"] == ["scan:run", "scan:read"]


async def test_create_api_key_rejects_an_unknown_scope(client, builder_account):
    response = await client.post(
        "/v1/me/api-keys", json={"name": "bad scopes", "scopes": ["not:a:real:scope"]}
    )
    assert response.status_code == 422


async def test_create_api_key_beyond_the_builder_plan_limit_is_denied(client, builder_account):
    # Builder's api_keys_limit is 1.
    first = await client.post(
        "/v1/me/api-keys", json={"name": "first", "scopes": ["scan:read"]}
    )
    assert first.status_code == 201

    second = await client.post(
        "/v1/me/api-keys", json={"name": "second", "scopes": ["scan:read"]}
    )
    assert second.status_code == 429
    assert second.json()["code"] == "QUOTA_EXCEEDED"


async def test_list_api_keys_never_returns_the_plaintext_or_hash(client, builder_account):
    await client.post("/v1/me/api-keys", json={"name": "listed key", "scopes": ["scan:read"]})

    response = await client.get("/v1/me/api-keys")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert "api_key" not in body[0]
    assert "key_hash" not in body[0]
    assert body[0]["prefix"]


async def test_revoke_api_key_requires_ownership(client, builder_account):
    create_response = await client.post(
        "/v1/me/api-keys", json={"name": "to revoke", "scopes": ["scan:read"]}
    )
    api_key_id = create_response.json()["api_key_id"]

    async with session_scope() as session:
        other = await get_or_create_account(
            session, email="apikey-other@example.com", clerk_user_id="user_apikey_other"
        )
    app.dependency_overrides[require_account] = lambda: other

    response = await client.post(f"/v1/me/api-keys/{api_key_id}/revoke")
    assert response.status_code == 404


async def test_revoke_api_key_succeeds_for_the_owner(client, builder_account):
    create_response = await client.post(
        "/v1/me/api-keys", json={"name": "to revoke", "scopes": ["scan:read"]}
    )
    api_key_id = create_response.json()["api_key_id"]

    response = await client.post(f"/v1/me/api-keys/{api_key_id}/revoke")

    assert response.status_code == 200
    assert response.json()["revoked_at"] is not None


async def test_revoke_an_unknown_api_key_returns_404(client, builder_account):
    response = await client.post(f"/v1/me/api-keys/{uuid.uuid4()}/revoke")
    assert response.status_code == 404


async def test_api_key_endpoints_require_authentication(client):
    response = await client.post(
        "/v1/me/api-keys", json={"name": "x", "scopes": ["scan:read"]}
    )
    assert response.status_code == 401
