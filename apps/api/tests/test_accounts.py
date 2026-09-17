from __future__ import annotations

from vigilo_api.deps import require_account
from vigilo_api.main import app
from vigilo_identity.repository import get_or_create_account
from vigilo_persistence import session_scope


async def test_get_me_returns_the_authenticated_account(client):
    async with session_scope() as session:
        account = await get_or_create_account(
            session, email="owner@example.com", clerk_user_id="user_x"
        )
    app.dependency_overrides[require_account] = lambda: account

    response = await client.get("/v1/me")

    assert response.status_code == 200
    body = response.json()
    assert body["email"] == "owner@example.com"
    assert body["status"] == "active"
    assert body["entitlements"] == {
        "plan_id": "free",
        "targets_limit": 1,
        "scans_per_month_limit": 3,
        "active_tier_allowed": False,
        "share_links_allowed": False,
        "monitoring_frequency": None,
        "monitors_limit": 0,
        "api_keys_limit": 0,
        "api_rate_limit_per_minute": None,
        "white_label_allowed": False,
        "repo_connectors_limit": None,
    }


async def test_get_me_requires_authentication(client):
    response = await client.get("/v1/me")
    assert response.status_code == 401
