"""The one call the CLI uses: probe a target and hand back a sealed bundle.

Concurrency, request budgets and cross-target politeness governance belong
to the Scan Orchestrator built in Phase 3 (docs/modules.md §8) — this is a
single-target convenience wrapper for the CLI's scope. TLS, well-known-path
and bundle probing are independent of each other and run concurrently
(docs/architecture.md driver #4, "low-latency perception"); the backend
probe runs after, since it needs the bundle probe's fetched script content.

`tier` gates the `paths` probe (Phase 6): it only runs at `Tier.ACTIVE`.
This is the probe-layer half of the tier-gating guarantee
(docs/adr/ADR-0003-scan-authorization-model.md) — an unverified target must
never receive the `paths` probe's hidden-path-enumeration requests at all,
not merely have the resulting findings filtered out afterward. Defaulting
to `Tier.PASSIVE` means the CLI (`apps/cli/src/vigilo_cli/main.py`, which
has no ownership-verification mechanism and must never claim active tier)
needs no changes at all.
"""

from __future__ import annotations

import asyncio

import httpx

from vigilo_core.evidence import EvidenceBundle, HttpObservation, TlsObservation
from vigilo_core.models import Tier
from vigilo_core.validation import validate_target_url
from vigilo_probes.backend_probe import run_backend_checks
from vigilo_probes.bundle_probe import run_bundle
from vigilo_probes.fingerprint import fingerprint as derive_fingerprint
from vigilo_probes.http_probe import run_http
from vigilo_probes.paths_probe import run_paths
from vigilo_probes.seal import seal
from vigilo_probes.tls_probe import run_tls
from vigilo_probes.wellknown_probe import run_wellknown
from vigilo_security.egress_guard import Resolver, validate_and_pin


async def _probe_tls(http: HttpObservation, resolver: Resolver | None) -> TlsObservation | None:
    if not http.url.startswith("https://"):
        return None
    conn = validate_and_pin(http.url, resolver=resolver)
    return await asyncio.to_thread(run_tls, conn.host, conn.pinned_ip, conn.port)


async def run_probes(
    url: str,
    tier: Tier = Tier.PASSIVE,
    resolver: Resolver | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
) -> EvidenceBundle:
    """`target_origin` on the returned bundle is the originally requested
    target; `http.url`/`http.redirect_chain` show where it actually landed.

    `transport` is exposed purely for testing (same contract as `run_http`)
    and is threaded through to every HTTP-based sub-probe; production
    callers never pass it.
    """
    target_origin = validate_target_url(url)

    http = await run_http(url, resolver=resolver, transport=transport)

    tls, wellknown, bundle_obs = await asyncio.gather(
        _probe_tls(http, resolver),
        run_wellknown(url, resolver=resolver, transport=transport),
        run_bundle(http, resolver=resolver, transport=transport),
    )

    backends = await run_backend_checks(bundle_obs, http, resolver=resolver, transport=transport)

    paths = None
    if tier == Tier.ACTIVE:
        paths = await run_paths(url, resolver=resolver, transport=transport)

    fp = derive_fingerprint(http)

    return seal(target_origin, http, tls, fp, bundle_obs, wellknown, backends, paths)
