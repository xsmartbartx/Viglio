"""Paddle integration (docs/modules.md §7's `billing` adapter, ADR-0002:
merchant of record). No SDK dependency, matching `mail.py`'s "a single
request is all the provider needs" posture, plus HMAC signature
verification for webhooks.

Paddle's webhook signature header (`Paddle-Signature`) is
`ts=<unix-timestamp>;h1=<hex-hmac-sha256>`, computed over
`f"{ts}:{raw_body}"` with the webhook secret — verified here exactly as
Paddle documents it, so this adapter needs no changes when a real account
replaces the stub, only real `PADDLE_*` env values
(`packages/core/src/vigilo_core/config.py`).

`create_checkout_url()` builds Paddle's hosted-checkout URL by template —
no server-to-server API call, so no `transport=` DI seam is needed there;
tests only need `monkeypatch.setenv`.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any
from urllib.parse import urlencode

from vigilo_core.config import config
from vigilo_integrations.errors import BillingProviderError

_CHECKOUT_BASE_URL = "https://checkout.paddle.com/checkout"

_PRICE_ID_ENV_FIELD = {
    "builder": "paddle_price_id_builder",
    "studio": "paddle_price_id_studio",
    "business": "paddle_price_id_business",
}


def verify_webhook_signature(raw_body: bytes, signature_header: str) -> bool:
    cfg = config()
    if not cfg.paddle_webhook_secret:
        raise BillingProviderError("Paddle is not configured (missing webhook secret)")

    try:
        parts = dict(item.split("=", 1) for item in signature_header.split(";"))
        timestamp, signature = parts["ts"], parts["h1"]
    except (KeyError, ValueError):
        return False

    signed_payload = f"{timestamp}:".encode() + raw_body
    expected = hmac.new(
        cfg.paddle_webhook_secret.encode(), signed_payload, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


def parse_webhook_event(raw_body: bytes) -> dict[str, Any]:
    try:
        return json.loads(raw_body)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise BillingProviderError("Paddle webhook body was not valid JSON") from exc


def create_checkout_url(plan_id: str, account_email: str, account_reference: str) -> str:
    cfg = config()
    if not cfg.paddle_vendor_id:
        raise BillingProviderError("Paddle is not configured (missing vendor id)")

    price_field = _PRICE_ID_ENV_FIELD.get(plan_id)
    price_id = getattr(cfg, price_field, None) if price_field else None
    if not price_id:
        raise BillingProviderError("no Paddle price configured for this plan", plan_id=plan_id)

    query = urlencode(
        {
            "vendor": cfg.paddle_vendor_id,
            "product": price_id,
            "customer_email": account_email,
            "passthrough": account_reference,
        }
    )
    return f"{_CHECKOUT_BASE_URL}?{query}"
