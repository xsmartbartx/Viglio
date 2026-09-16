from __future__ import annotations

import hashlib
import hmac
import json

import pytest

from vigilo_api.deps import require_account
from vigilo_api.main import app
from vigilo_core.config import config
from vigilo_identity.repository import get_account_by_id, get_or_create_account
from vigilo_persistence import session_scope

_SECRET = "whsec_test"


@pytest.fixture(autouse=True)
def _paddle_configured(monkeypatch):
    monkeypatch.setenv("PADDLE_VENDOR_ID", "12345")
    monkeypatch.setenv("PADDLE_WEBHOOK_SECRET", _SECRET)
    monkeypatch.setenv("PADDLE_PRICE_ID_BUILDER", "pri_builder")
    monkeypatch.setenv("PADDLE_PRICE_ID_STUDIO", "pri_studio")
    config.cache_clear()
    yield
    config.cache_clear()


def _signed_header(raw_body: bytes, timestamp: str = "1700000000") -> str:
    signed_payload = f"{timestamp}:".encode() + raw_body
    signature = hmac.new(_SECRET.encode(), signed_payload, hashlib.sha256).hexdigest()
    return f"ts={timestamp};h1={signature}"


async def test_checkout_requires_authentication(client):
    response = await client.post("/v1/billing/checkout", json={"plan_id": "builder"})
    assert response.status_code == 401


async def test_checkout_returns_a_paddle_url_for_a_priced_plan(client):
    async with session_scope() as session:
        account = await get_or_create_account(session, email="checkout@example.com")
    app.dependency_overrides[require_account] = lambda: account

    response = await client.post("/v1/billing/checkout", json={"plan_id": "builder"})

    assert response.status_code == 200
    url = response.json()["checkout_url"]
    assert url.startswith("https://checkout.paddle.com/checkout?")
    assert "product=pri_builder" in url


async def test_checkout_for_an_unpriced_plan_returns_500(client):
    async with session_scope() as session:
        account = await get_or_create_account(session, email="freecheckout@example.com")
    app.dependency_overrides[require_account] = lambda: account

    response = await client.post("/v1/billing/checkout", json={"plan_id": "free"})

    assert response.status_code == 500
    assert response.json()["code"] == "BILLING_PROVIDER_ERROR"


async def test_webhook_rejects_an_invalid_signature(client):
    raw_body = json.dumps({"event_type": "subscription.created"}).encode()

    response = await client.post(
        "/v1/billing/webhook",
        content=raw_body,
        headers={"Paddle-Signature": "ts=1;h1=not-the-real-signature"},
    )

    assert response.status_code == 401


async def test_webhook_ignores_an_unrecognized_event_type(client):
    raw_body = json.dumps({"event_type": "invoice.paid", "data": {}}).encode()

    response = await client.post(
        "/v1/billing/webhook",
        content=raw_body,
        headers={"Paddle-Signature": _signed_header(raw_body)},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "ignored"


async def test_webhook_ignores_an_event_for_an_unknown_account(client):
    payload = {
        "event_type": "subscription.created",
        "data": {
            "subscription_id": "sub_unknown",
            "customer": {"email": "never-signed-up@example.com"},
            "plan_id": "builder",
        },
    }
    raw_body = json.dumps(payload).encode()

    response = await client.post(
        "/v1/billing/webhook",
        content=raw_body,
        headers={"Paddle-Signature": _signed_header(raw_body)},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "ignored"


async def test_webhook_upgrades_a_known_account_to_the_new_plan(client):
    async with session_scope() as session:
        account = await get_or_create_account(session, email="webhook-upgrade@example.com")

    payload = {
        "event_type": "subscription.created",
        "data": {
            "subscription_id": "sub_webhook_upgrade",
            "customer": {"email": "webhook-upgrade@example.com"},
            "plan_id": "builder",
        },
    }
    raw_body = json.dumps(payload).encode()

    response = await client.post(
        "/v1/billing/webhook",
        content=raw_body,
        headers={"Paddle-Signature": _signed_header(raw_body)},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "applied"

    async with session_scope() as session:
        updated = await get_account_by_id(session, account.id)
    assert updated.plan_id == "builder"


async def test_webhook_cancellation_resets_the_account_to_free(client):
    async with session_scope() as session:
        account = await get_or_create_account(session, email="webhook-cancel@example.com")

    created_payload = {
        "event_type": "subscription.created",
        "data": {
            "subscription_id": "sub_webhook_cancel",
            "customer": {"email": "webhook-cancel@example.com"},
            "plan_id": "studio",
        },
    }
    created_body = json.dumps(created_payload).encode()
    await client.post(
        "/v1/billing/webhook",
        content=created_body,
        headers={"Paddle-Signature": _signed_header(created_body)},
    )

    canceled_payload = {
        "event_type": "subscription.canceled",
        "data": {
            "subscription_id": "sub_webhook_cancel",
            "customer": {"email": "webhook-cancel@example.com"},
            "plan_id": "studio",
        },
    }
    canceled_body = json.dumps(canceled_payload).encode()
    response = await client.post(
        "/v1/billing/webhook",
        content=canceled_body,
        headers={"Paddle-Signature": _signed_header(canceled_body)},
    )

    assert response.status_code == 200

    async with session_scope() as session:
        updated = await get_account_by_id(session, account.id)
    assert updated.plan_id == "free"
