from __future__ import annotations

import pytest_asyncio

from vigilo_api.deps import require_account
from vigilo_api.main import app
from vigilo_identity.repository import (
    get_account_by_id,
    get_or_create_account,
    upsert_subscription,
)
from vigilo_persistence import session_scope


async def _upgrade_to(account_id, email: str, plan_id: str):
    async with session_scope() as session:
        await upsert_subscription(
            session,
            account_id=account_id,
            plan_id=plan_id,
            status="active",
            provider="paddle",
            provider_subscription_id=f"sub_{email}",
            current_period_end=None,
        )
        return await get_account_by_id(session, account_id)


@pytest_asyncio.fixture
async def business_account():
    async with session_scope() as session:
        acc = await get_or_create_account(
            session, email="branding-business@example.com", clerk_user_id="user_branding_biz"
        )
    acc = await _upgrade_to(acc.id, acc.email, "business")
    app.dependency_overrides[require_account] = lambda: acc
    yield acc
    app.dependency_overrides.pop(require_account, None)


@pytest_asyncio.fixture
async def studio_account():
    async with session_scope() as session:
        acc = await get_or_create_account(
            session, email="branding-studio@example.com", clerk_user_id="user_branding_studio"
        )
    acc = await _upgrade_to(acc.id, acc.email, "studio")
    app.dependency_overrides[require_account] = lambda: acc
    yield acc
    app.dependency_overrides.pop(require_account, None)


async def test_update_branding_profile_on_studio_is_denied(client, studio_account):
    response = await client.put(
        "/v1/me/branding-profile", json={"logo_url": "https://example.com/logo.png"}
    )
    assert response.status_code == 429
    assert response.json()["code"] == "QUOTA_EXCEEDED"


async def test_update_branding_profile_on_business_succeeds(client, business_account):
    response = await client.put(
        "/v1/me/branding-profile",
        json={
            "logo_url": "https://example.com/logo.png",
            "primary_color": "#112233",
            "footer_text": "Provided by Acme Security",
            "custom_domain": "reports.acme.example.com",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["logo_url"] == "https://example.com/logo.png"
    assert body["primary_color"] == "#112233"


async def test_get_branding_profile_before_any_update_is_all_null(client, business_account):
    response = await client.get("/v1/me/branding-profile")

    assert response.status_code == 200
    assert response.json() == {
        "logo_url": None,
        "primary_color": None,
        "footer_text": None,
        "custom_domain": None,
    }


async def test_branding_profile_endpoints_require_authentication(client):
    response = await client.get("/v1/me/branding-profile")
    assert response.status_code == 401


async def test_update_branding_profile_is_a_partial_update(client, business_account):
    await client.put(
        "/v1/me/branding-profile",
        json={"logo_url": "https://example.com/logo.png", "primary_color": "#112233"},
    )

    response = await client.put(
        "/v1/me/branding-profile", json={"footer_text": "Provided by Acme Security"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["footer_text"] == "Provided by Acme Security"
    assert body["logo_url"] == "https://example.com/logo.png"
    assert body["primary_color"] == "#112233"
