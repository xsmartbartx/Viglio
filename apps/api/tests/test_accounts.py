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


async def test_get_me_requires_authentication(client):
    response = await client.get("/v1/me")
    assert response.status_code == 401
