from __future__ import annotations

import hashlib
import hmac
import json

import pytest

from vigilo_core.config import config
from vigilo_integrations.billing import (
    create_checkout_url,
    parse_webhook_event,
    verify_webhook_signature,
)
from vigilo_integrations.errors import BillingProviderError

_SECRET = "whsec_test"


@pytest.fixture(autouse=True)
def _paddle_configured(monkeypatch):
    monkeypatch.setenv("PADDLE_VENDOR_ID", "12345")
    monkeypatch.setenv("PADDLE_WEBHOOK_SECRET", _SECRET)
    monkeypatch.setenv("PADDLE_PRICE_ID_BUILDER", "pri_builder")
    monkeypatch.setenv("PADDLE_PRICE_ID_STUDIO", "pri_studio")
    monkeypatch.setenv("PADDLE_PRICE_ID_BUSINESS", "pri_business")
    config.cache_clear()
    yield
    config.cache_clear()


def _signed_header(raw_body: bytes, timestamp: str = "1700000000") -> str:
    signed_payload = f"{timestamp}:".encode() + raw_body
    signature = hmac.new(_SECRET.encode(), signed_payload, hashlib.sha256).hexdigest()
    return f"ts={timestamp};h1={signature}"


def test_verify_webhook_signature_accepts_a_valid_signature():
    raw_body = b'{"event_type":"subscription.created"}'
    header = _signed_header(raw_body)
    assert verify_webhook_signature(raw_body, header) is True


def test_verify_webhook_signature_rejects_a_tampered_body():
    raw_body = b'{"event_type":"subscription.created"}'
    header = _signed_header(raw_body)
    assert verify_webhook_signature(b'{"event_type":"subscription.canceled"}', header) is False


def test_verify_webhook_signature_rejects_a_malformed_header():
    raw_body = b"{}"
    assert verify_webhook_signature(raw_body, "not-a-valid-header") is False


def test_verify_webhook_signature_raises_when_not_configured(monkeypatch):
    monkeypatch.delenv("PADDLE_WEBHOOK_SECRET", raising=False)
    config.cache_clear()

    with pytest.raises(BillingProviderError):
        verify_webhook_signature(b"{}", "ts=1;h1=abc")


def test_parse_webhook_event_returns_the_decoded_payload():
    raw_body = json.dumps({"event_type": "subscription.created", "data": {}}).encode()
    assert parse_webhook_event(raw_body) == {"event_type": "subscription.created", "data": {}}


def test_parse_webhook_event_raises_on_invalid_json():
    with pytest.raises(BillingProviderError):
        parse_webhook_event(b"not json")


def test_create_checkout_url_builds_a_paddle_url():
    url = create_checkout_url("builder", "owner@example.com", "account-ref-123")
    assert url.startswith("https://checkout.paddle.com/checkout?")
    assert "product=pri_builder" in url
    assert "owner%40example.com" in url


def test_create_checkout_url_builds_a_paddle_url_for_business():
    url = create_checkout_url("business", "owner@example.com", "account-ref-123")
    assert "product=pri_business" in url


def test_create_checkout_url_raises_when_vendor_id_unset(monkeypatch):
    monkeypatch.delenv("PADDLE_VENDOR_ID", raising=False)
    config.cache_clear()

    with pytest.raises(BillingProviderError):
        create_checkout_url("builder", "owner@example.com", "account-ref-123")


def test_create_checkout_url_raises_for_an_unpriced_plan():
    with pytest.raises(BillingProviderError):
        create_checkout_url("free", "owner@example.com", "account-ref-123")
