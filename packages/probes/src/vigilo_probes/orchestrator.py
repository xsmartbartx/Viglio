"""The one call the CLI uses: probe a target and hand back a sealed bundle.

Concurrency, request budgets and cross-target politeness governance belong
to the Scan Orchestrator built in Phase 3 (docs/modules.md §8) — this is a
single-target convenience wrapper for Phase 1's CLI-only scope.
"""

from __future__ import annotations

import asyncio

from vigilo_core.evidence import EvidenceBundle, TlsObservation
from vigilo_core.validation import validate_target_url
from vigilo_security.egress_guard import Resolver, validate_and_pin

from vigilo_probes.fingerprint import fingerprint as derive_fingerprint
from vigilo_probes.http_probe import run_http
from vigilo_probes.seal import seal
from vigilo_probes.tls_probe import run_tls


async def run_probes(url: str, resolver: Resolver | None = None) -> EvidenceBundle:
    """`target_origin` on the returned bundle is the originally requested
    target; `http.url`/`http.redirect_chain` show where it actually landed."""
    target_origin = validate_target_url(url)

    http = await run_http(url, resolver=resolver)

    tls: TlsObservation | None = None
    if http.url.startswith("https://"):
        conn = validate_and_pin(http.url, resolver=resolver)
        tls = await asyncio.to_thread(run_tls, conn.host, conn.pinned_ip, conn.port)

    fp = derive_fingerprint(http)

    return seal(target_origin, http, tls, fp)
