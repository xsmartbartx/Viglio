"""The well-known probe: presence of a fixed, small set of conventionally
public paths. Explicitly passive-tier per docs/vision.md ("GET on public
.well-known paths") — distinct from the Tier-1-only `paths` probe
(docs/modules.md §3), which blindly enumerates a much larger, non-conventional
path list and requires verified ownership.

Own `validate_and_pin` call rather than reusing `run_http`'s connection —
one extra DNS resolution per scan, same pattern the orchestrator already uses
for `tls_probe`. Keeps this probe independent and simple to test.
"""

from __future__ import annotations

import httpx
from vigilo_core.evidence import WellKnownObservation
from vigilo_probes.http_probe import build_pinned_url
from vigilo_security.egress_guard import Resolver, validate_and_pin

_REQUEST_TIMEOUT = 10.0
_USER_AGENT = "VigiloScanner/0.1 (+https://vigilo.io/scanner)"

_PATHS = {
    "security_txt_present": "/.well-known/security.txt",
    "robots_txt_present": "/robots.txt",
    "sitemap_present": "/sitemap.xml",
    "manifest_present": "/manifest.json",
}


async def run_wellknown(
    url: str,
    resolver: Resolver | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
) -> WellKnownObservation:
    conn = validate_and_pin(url, resolver=resolver)
    results: dict[str, bool] = {}

    async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT, transport=transport) as client:
        for field, path in _PATHS.items():
            request_url = build_pinned_url(conn, path)
            try:
                response = await client.get(
                    request_url,
                    headers={"Host": conn.host, "User-Agent": _USER_AGENT},
                    extensions={"sni_hostname": conn.host},
                )
            except httpx.HTTPError:
                results[field] = False
                continue
            results[field] = response.status_code == 200

    return WellKnownObservation(**results)
