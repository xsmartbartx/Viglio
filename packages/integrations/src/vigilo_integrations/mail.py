"""Transactional email via Postmark's plain HTTP API (docs/modules.md §7's
`mail` adapter). No SDK dependency — a single POST is all Postmark needs.

`transport` is the same dependency-injection seam used throughout the
codebase (`httpx.MockTransport` in tests) so no test ever sends a real email.
"""

from __future__ import annotations

import httpx
from vigilo_core.config import config

from vigilo_integrations.errors import MailDeliveryFailed

_POSTMARK_URL = "https://api.postmarkapp.com/email"
_REQUEST_TIMEOUT = 10.0


async def send_transactional_email(
    to: str,
    subject: str,
    html_body: str,
    text_body: str | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
) -> None:
    cfg = config()
    if not cfg.postmark_server_token or not cfg.mail_from_address:
        raise MailDeliveryFailed("Postmark is not configured (missing server token or from address)")

    payload = {
        "From": cfg.mail_from_address,
        "To": to,
        "Subject": subject,
        "HtmlBody": html_body,
        "TextBody": text_body or "",
        "MessageStream": "outbound",
    }
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "X-Postmark-Server-Token": cfg.postmark_server_token,
    }

    try:
        async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT, transport=transport) as client:
            response = await client.post(_POSTMARK_URL, json=payload, headers=headers)
    except httpx.HTTPError as exc:
        raise MailDeliveryFailed("Postmark request failed", to=to) from exc

    if response.status_code >= 400:
        raise MailDeliveryFailed(
            "Postmark rejected the message", to=to, status_code=response.status_code
        )
