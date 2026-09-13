"""verify_ownership(): the four ADR-0003 ownership-proof methods.

Two of the four (`wellknown_file`, `meta_tag`) fetch the target's own
origin — SSRF-relevant code. They call `validate_and_pin()` first and
connect to the literal pinned IP, exactly like `packages/probes` does; this
module must never fetch a hostname it hasn't pinned. `dns_txt` looks up a
TXT record via an injectable resolver (distinct from `egress_guard.Resolver`,
which only returns A/AAAA addresses) so tests never touch real DNS. `email`
needs a click-through confirmation flow that doesn't exist before Phase 4
(docs/build-roadmap.md's Phase 3 scope trim) — stubbed here, not implemented.

Per the Phase 3 ADR-0003 addendum, every one of these methods is dispatched
from `verify_ownership_job` inside the ARQ worker (`apps/scanner`), never
called synchronously from `apps/api` — "the control plane never makes an
outbound request to a target, ever" (docs/architecture.md §3). This module
itself is transport-agnostic; it doesn't enforce where it's called from.
"""

from __future__ import annotations

import asyncio
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

import httpx

from vigilo_core.config import config
from vigilo_core.models import VerificationMethod
from vigilo_security.egress_guard import Resolver, ValidatedConnection, validate_and_pin
from vigilo_security.exceptions import VerificationIOError

TxtResolver = Callable[[str], list[str]]
"""Returns the raw TXT record strings for a hostname. Tests inject a fake
resolver so this module never touches real DNS, the same rule
`egress_guard.Resolver` follows for A/AAAA lookups."""

_REQUEST_TIMEOUT = 10.0
_MAX_BYTES = 64 * 1024
_USER_AGENT = "VigiloScanner/0.1 (+https://vigilo.io/scanner)"
_META_TAG_PATTERN = re.compile(
    r'<meta\s+[^>]*name=["\']vigilo-site-verification["\'][^>]*content=["\']([^"\']+)["\']',
    re.IGNORECASE,
)
_DEFAULT_DNS_KEY = "vigilo-site-verification"
_DEFAULT_WELLKNOWN_PATH = "/.well-known/vigilo-verification.txt"


@dataclass(frozen=True)
class VerificationResult:
    verified: bool
    method: VerificationMethod
    detail: str
    checked_at: datetime


def _host_of(origin: str) -> str:
    _scheme, _, rest = origin.partition("://")
    host, _, _port = rest.partition(":")
    return host


def _build_pinned_url(conn: ValidatedConnection, path: str = "/") -> str:
    """Small, deliberate duplicate of `vigilo_probes.http_probe
    .build_pinned_url` — `packages/security` must not depend on
    `vigilo_probes` (probes depends on security, not the reverse, per
    docs/modules.md's dependency graph)."""
    scheme = conn.origin.split("://", 1)[0]
    host = f"[{conn.pinned_ip}]" if ":" in conn.pinned_ip else conn.pinned_ip
    return f"{scheme}://{host}:{conn.port}{path}"


async def _fetch_bounded(
    conn: ValidatedConnection,
    path: str,
    transport: httpx.AsyncBaseTransport | None,
) -> str | None:
    """GET a pinned-connection path, capped at `_MAX_BYTES`. Returns the
    decoded body, or `None` on any non-2xx status or transport error — a
    fetch failure means "not verified yet," not a hard I/O error, since a
    missing file/tag is the expected state before the owner has acted."""
    request_url = _build_pinned_url(conn, path)
    try:
        client = httpx.AsyncClient(timeout=_REQUEST_TIMEOUT, transport=transport)
        async with client, client.stream(
            "GET",
            request_url,
            headers={"Host": conn.host, "User-Agent": _USER_AGENT},
            extensions={"sni_hostname": conn.host},
        ) as response:
            if response.status_code != 200:
                return None
            chunks: list[bytes] = []
            downloaded = 0
            async for chunk in response.aiter_bytes():
                downloaded += len(chunk)
                chunks.append(chunk)
                if downloaded >= _MAX_BYTES:
                    break
            return b"".join(chunks).decode(errors="replace")
    except httpx.HTTPError:
        return None


def _default_txt_resolver(hostname: str) -> list[str]:
    import dns.resolver

    answer = dns.resolver.resolve(hostname, "TXT")
    return ["".join(part.decode() for part in rdata.strings) for rdata in answer]


def verify_dns_txt(
    origin: str, expected_nonce: str, txt_resolver: TxtResolver | None = None
) -> VerificationResult:
    resolve = txt_resolver or _default_txt_resolver
    host = _host_of(origin)
    key = config().brand.namespaces.get("dnsVerificationKey", _DEFAULT_DNS_KEY)
    expected = f"{key}={expected_nonce}"

    try:
        records = resolve(host)
    except Exception as exc:
        raise VerificationIOError("DNS TXT lookup failed", host=host) from exc

    verified = any(expected in record for record in records)
    return VerificationResult(
        verified=verified,
        method=VerificationMethod.DNS_TXT,
        detail="matching TXT record found" if verified else "no matching TXT record found",
        checked_at=datetime.now(UTC),
    )


async def verify_wellknown_file(
    origin: str,
    expected_nonce: str,
    resolver: Resolver | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
) -> VerificationResult:
    conn = validate_and_pin(origin, resolver=resolver)
    path = config().brand.namespaces.get("wellKnownPath", _DEFAULT_WELLKNOWN_PATH)
    body = await _fetch_bounded(conn, path, transport)

    verified = body is not None and body.strip() == expected_nonce
    return VerificationResult(
        verified=verified,
        method=VerificationMethod.WELLKNOWN_FILE,
        detail="well-known file content matches" if verified else "well-known file absent or mismatched",
        checked_at=datetime.now(UTC),
    )


async def verify_meta_tag(
    origin: str,
    expected_nonce: str,
    resolver: Resolver | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
) -> VerificationResult:
    conn = validate_and_pin(origin, resolver=resolver)
    body = await _fetch_bounded(conn, "/", transport)

    match = _META_TAG_PATTERN.search(body) if body else None
    verified = match is not None and match.group(1) == expected_nonce
    return VerificationResult(
        verified=verified,
        method=VerificationMethod.META_TAG,
        detail="meta tag content matches" if verified else "meta tag absent or mismatched",
        checked_at=datetime.now(UTC),
    )


async def verify_email(origin: str, expected_nonce: str) -> VerificationResult:
    """Not implemented in Phase 3 — needs a click-through confirmation flow
    (send a token to an address at the target's registered domain, wait for
    the owner to click it) that has no home before Phase 4's dashboard.
    DNS-TXT/well-known-file/meta-tag already satisfy the exit criterion's
    own wording ("I've placed the record/file/tag, check now")."""
    raise NotImplementedError("email ownership verification ships in Phase 4")


async def verify_ownership(
    method: VerificationMethod,
    origin: str,
    expected_nonce: str,
    resolver: Resolver | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
    txt_resolver: TxtResolver | None = None,
) -> VerificationResult:
    if method == VerificationMethod.DNS_TXT:
        return await asyncio.to_thread(verify_dns_txt, origin, expected_nonce, txt_resolver)
    if method == VerificationMethod.WELLKNOWN_FILE:
        return await verify_wellknown_file(origin, expected_nonce, resolver=resolver, transport=transport)
    if method == VerificationMethod.META_TAG:
        return await verify_meta_tag(origin, expected_nonce, resolver=resolver, transport=transport)
    return await verify_email(origin, expected_nonce)
