"""The `paths` probe: blind enumeration of a fixed, published, non-conventional
path list (docs/modules.md §3) — repository metadata, backup artefacts,
exposed configuration, debug/test routes, directory listings, default admin
panels. Explicitly **Tier 1 (active, verified-ownership) only**, distinct
from `wellknown_probe.py`'s conventionally-public paths
(docs/adr/ADR-0003-scan-authorization-model.md's Phase 2 addendum: shipping
this against an unverified target would be blind hidden-path enumeration, a
direct violation of the passive-tier definition). The tier gate itself lives
in `orchestrator.py`, which only calls `run_paths()` at `Tier.ACTIVE` — this
module has no tier awareness of its own, matching every other probe.

Same architecture as `wellknown_probe.py`, not `backend_probe.py`: one
`validate_and_pin()` call against the *same* target origin the whole scan
already validated, then N bounded GETs of *fixed relative paths* — no new
hostname is ever discovered or resolved here, so this carries no
provider-specific SSRF surface beyond what `test_egress_guard.py` already
covers generically for the single `validate_and_pin` call.
"""

from __future__ import annotations

import re

import httpx

from vigilo_core.evidence import DetectedPath, PathObservation
from vigilo_probes.http_probe import build_pinned_url
from vigilo_security.egress_guard import Resolver, ValidatedConnection, validate_and_pin

_REQUEST_TIMEOUT = 10.0
_MAX_BYTES = 64 * 1024
_USER_AGENT = "VigiloScanner/0.1 (+https://vigilo.io/scanner)"

# Small, fixed, published candidate list — not a wordlist scan. Each entry:
# (path, kind). Every kind is aggregated by packages/checks/src/vigilo_checks
# /exp.py's VG-EXP-006..012 into one finding per kind.
_CANDIDATES: list[tuple[str, str]] = [
    # repository metadata
    ("/.git/HEAD", "repo_metadata"),
    ("/.git/config", "repo_metadata"),
    ("/.svn/entries", "repo_metadata"),
    ("/.hg/", "repo_metadata"),
    # backup artefacts
    ("/backup.zip", "backup_artefact"),
    ("/backup.sql", "backup_artefact"),
    ("/db.sql", "backup_artefact"),
    ("/site.tar.gz", "backup_artefact"),
    ("/.env.bak", "backup_artefact"),
    # exposed configuration
    ("/.env", "exposed_config"),
    ("/config.json", "exposed_config"),
    ("/appsettings.json", "exposed_config"),
    ("/wp-config.php.bak", "exposed_config"),
    # debug routes
    ("/debug", "debug_route"),
    ("/_debug", "debug_route"),
    ("/phpinfo.php", "debug_route"),
    ("/actuator", "debug_route"),
    ("/actuator/health", "debug_route"),
    # test/staging routes
    ("/test", "test_route"),
    ("/staging", "test_route"),
    ("/_test", "test_route"),
    ("/api/test", "test_route"),
    # directory listing
    ("/uploads/", "directory_listing"),
    ("/assets/", "directory_listing"),
    ("/backup/", "directory_listing"),
    ("/files/", "directory_listing"),
    # default admin panels
    ("/wp-admin/", "admin_panel"),
    ("/admin/", "admin_panel"),
    ("/administrator/", "admin_panel"),
]

_LISTING_MARKERS = re.compile(r"<title>\s*index of|directory listing for", re.IGNORECASE)


async def _check_path(
    client: httpx.AsyncClient, conn: ValidatedConnection, path: str, kind: str
) -> DetectedPath | None:
    request_url = build_pinned_url(conn, path)
    try:
        async with client.stream(
            "GET",
            request_url,
            headers={"Host": conn.host, "User-Agent": _USER_AGENT},
            extensions={"sni_hostname": conn.host},
        ) as response:
            if response.status_code != 200:
                return None
            body = bytearray()
            async for chunk in response.aiter_bytes():
                body.extend(chunk)
                if len(body) >= _MAX_BYTES:
                    break
            text = bytes(body).decode("utf-8", errors="replace")
    except httpx.HTTPError:
        return None

    if kind == "directory_listing":
        if not _LISTING_MARKERS.search(text):
            return None
        return DetectedPath(path=path, kind=kind, status_code=200, indicator="autoindex response")

    return DetectedPath(path=path, kind=kind, status_code=200, indicator=f"HTTP 200 at {path}")


async def run_paths(
    url: str,
    resolver: Resolver | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
) -> PathObservation:
    conn = validate_and_pin(url, resolver=resolver)
    checked: list[str] = []
    detected: list[DetectedPath] = []

    async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT, transport=transport) as client:
        for path, kind in _CANDIDATES:
            checked.append(path)
            hit = await _check_path(client, conn, path, kind)
            if hit is not None:
                detected.append(hit)

    return PathObservation(checked=checked, detected=detected)
