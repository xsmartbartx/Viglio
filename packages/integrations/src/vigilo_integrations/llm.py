"""Claude-backed text generation via Anthropic's Messages API (docs/modules.md
§7's `llm` adapter). No SDK dependency — a single POST, same posture as
`mail.py`'s Postmark integration.

`transport` is the same dependency-injection seam used throughout the
codebase (`httpx.MockTransport` in tests) so no test ever calls a real
provider. This module validates only the HTTP/transport-level response shape
(a 2xx with text content) — the Vigilo-domain JSON schema inside that text
(`explanation`/`impact`/etc.) is `vigilo_reporting.remediation`'s concern,
one layer up, per docs/adr/ADR-0004-llm-boundary.md.
"""

from __future__ import annotations

import httpx

from vigilo_core.config import config
from vigilo_integrations.errors import LlmProviderError

_ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
_ANTHROPIC_VERSION = "2023-06-01"
_REQUEST_TIMEOUT = 30.0
_MAX_TOKENS = 1024


async def generate_remediation_text(
    prompt: str,
    system: str | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
) -> str:
    cfg = config()
    if not cfg.anthropic_api_key:
        raise LlmProviderError("Anthropic is not configured (missing API key)")

    payload: dict[str, object] = {
        "model": cfg.anthropic_model,
        "max_tokens": _MAX_TOKENS,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        payload["system"] = system

    headers = {
        "content-type": "application/json",
        "x-api-key": cfg.anthropic_api_key,
        "anthropic-version": _ANTHROPIC_VERSION,
    }

    try:
        async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT, transport=transport) as client:
            response = await client.post(_ANTHROPIC_URL, json=payload, headers=headers)
    except httpx.HTTPError as exc:
        raise LlmProviderError("Anthropic request failed") from exc

    if response.status_code >= 400:
        raise LlmProviderError(
            "Anthropic rejected the request", status_code=response.status_code
        )

    try:
        body = response.json()
        text = "".join(
            block["text"] for block in body["content"] if block.get("type") == "text"
        )
    except (ValueError, KeyError, TypeError) as exc:
        raise LlmProviderError("Anthropic response had no usable text content") from exc

    if not text:
        raise LlmProviderError("Anthropic response had no usable text content")

    return text
