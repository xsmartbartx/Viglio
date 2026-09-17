"""A thin `httpx` client of the public REST API (`/public/v1/*`,
`apps/api/src/vigilo_api/routers/public_api.py`) — this server has no
`vigilo_*` dependency and never touches the database directly; it's just
another API consumer, authenticated the same way any third-party
integration would be.

`transport` is the same dependency-injection seam used throughout the
codebase (`httpx.MockTransport` in tests) — matching `packages/
integrations/src/vigilo_integrations/mail.py`'s exact pattern.
"""

from __future__ import annotations

import os
from typing import Any

import httpx

_DEFAULT_BASE_URL = "http://localhost:8000"


class VigiloApiError(Exception):
    def __init__(self, status_code: int, body: dict[str, Any]) -> None:
        self.status_code = status_code
        self.body = body
        super().__init__(f"Vigilo API request failed ({status_code}): {body}")


def _base_url() -> str:
    return os.environ.get("VIGILO_API_BASE_URL", _DEFAULT_BASE_URL)


def _api_key() -> str:
    key = os.environ.get("VIGILO_API_KEY")
    if not key:
        raise RuntimeError("VIGILO_API_KEY is not set")
    return key


async def _request(
    method: str,
    path: str,
    transport: httpx.AsyncBaseTransport | None = None,
    **kwargs: Any,
) -> Any:
    headers = {"Authorization": f"Bearer {_api_key()}"}
    async with httpx.AsyncClient(
        base_url=_base_url(), timeout=30.0, transport=transport
    ) as client:
        response = await client.request(method, path, headers=headers, **kwargs)
    if response.status_code >= 400:
        try:
            body = response.json()
        except ValueError:
            body = {"detail": response.text}
        raise VigiloApiError(response.status_code, body)
    return response.json()


async def submit_scan(
    target_url: str,
    requested_tier: str = "passive",
    transport: httpx.AsyncBaseTransport | None = None,
) -> dict[str, Any]:
    return await _request(
        "POST",
        "/public/v1/scans",
        transport=transport,
        json={"target_url": target_url, "requested_tier": requested_tier},
    )


async def get_scan_status(
    scan_job_id: str, transport: httpx.AsyncBaseTransport | None = None
) -> dict[str, Any]:
    return await _request("GET", f"/public/v1/scans/{scan_job_id}", transport=transport)


async def get_scan_report(
    scan_job_id: str, transport: httpx.AsyncBaseTransport | None = None
) -> dict[str, Any]:
    return await _request(
        "GET", f"/public/v1/scans/{scan_job_id}/report", transport=transport
    )


async def get_scan_findings(
    scan_job_id: str, transport: httpx.AsyncBaseTransport | None = None
) -> list[dict[str, Any]]:
    return await _request(
        "GET", f"/public/v1/scans/{scan_job_id}/findings", transport=transport
    )
