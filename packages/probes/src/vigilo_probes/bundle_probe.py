"""The bundle probe: fetches the actual content of `<script src>` references
found in the homepage response. Fetching linked assets is explicitly
passive-tier per docs/vision.md ("homepage and linked assets") — the
scanner only ever follows links the page itself contains, never guesses at
paths.

**Every script URL goes through the egress guard before fetching — same
origin or third-party CDN, no exceptions.** A third-party script host is
exactly the kind of thing a hostile or compromised page could point at an
internal address, so this is not optional hardening; it's the same rule the
root page fetch already follows.
"""

from __future__ import annotations

import re
from urllib.parse import urljoin, urlsplit

import httpx

from vigilo_core.evidence import BundleObservation, FetchedScript, HttpObservation
from vigilo_core.validation import ValidationError
from vigilo_probes.http_probe import build_pinned_url
from vigilo_security import EgressDenied
from vigilo_security.egress_guard import Resolver, validate_and_pin

_SCRIPT_SRC_PATTERN = re.compile(r'<script\b[^>]*\bsrc\s*=\s*["\']([^"\']+)["\']', re.IGNORECASE)
_MAX_SCRIPTS = 5
_MAX_SCRIPT_BYTES = 256 * 1024
_REQUEST_TIMEOUT = 10.0
_USER_AGENT = "VigiloScanner/0.1 (+https://vigilo.io/scanner)"


def _extract_script_urls(http: HttpObservation) -> list[str]:
    seen: dict[str, None] = {}  # ordered de-dupe
    for match in _SCRIPT_SRC_PATTERN.finditer(http.body_excerpt):
        raw_src = match.group(1)
        if raw_src.startswith("data:"):
            continue
        absolute = urljoin(http.url, raw_src)
        seen.setdefault(absolute, None)
    return list(seen)[:_MAX_SCRIPTS]


async def _fetch_one(
    client: httpx.AsyncClient, url: str, resolver: Resolver | None
) -> FetchedScript:
    try:
        conn = validate_and_pin(url, resolver=resolver)
    except (ValidationError, EgressDenied) as exc:
        return FetchedScript(url=url, fetch_error=f"{exc.code.value}: {exc.message}")

    request_url = build_pinned_url(conn, _path_of(url))
    try:
        async with client.stream(
            "GET",
            request_url,
            headers={"Host": conn.host, "User-Agent": _USER_AGENT},
            extensions={"sni_hostname": conn.host},
        ) as response:
            chunks = bytearray()
            async for chunk in response.aiter_bytes():
                chunks.extend(chunk)
                if len(chunks) >= _MAX_SCRIPT_BYTES:
                    break
            body = bytes(chunks)
            return FetchedScript(
                url=url,
                status_code=response.status_code,
                size=len(body),
                excerpt=body.decode("utf-8", errors="replace"),
            )
    except httpx.HTTPError as exc:
        return FetchedScript(url=url, fetch_error=str(exc))


def _path_of(url: str) -> str:
    # Preserve the script's own path+query when connecting to the pinned IP —
    # build_pinned_url only supplies scheme://host:port, the path is ours to add.
    parts = urlsplit(url)
    path = parts.path or "/"
    return f"{path}?{parts.query}" if parts.query else path


async def run_bundle(
    http: HttpObservation,
    resolver: Resolver | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
) -> BundleObservation:
    urls = _extract_script_urls(http)
    if not urls:
        return BundleObservation()

    async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT, transport=transport) as client:
        fetched = [await _fetch_one(client, url, resolver) for url in urls]

    return BundleObservation(fetched_scripts=fetched)
