"""Vigilo probes: collect evidence about a target. This is the only module
permitted to make outbound requests to a target (docs/modules.md §3).

A probe records what happened; it never interprets, never assigns severity,
never imports `vigilo_checks`. It cannot decide its own request budget — that
governance belongs to the Scan Orchestrator (Phase 3).
"""

from vigilo_probes.backend_probe import run_backend_checks
from vigilo_probes.bundle_probe import run_bundle
from vigilo_probes.fingerprint import fingerprint
from vigilo_probes.http_probe import TooManyRedirects, build_pinned_url, run_http
from vigilo_probes.orchestrator import run_probes
from vigilo_probes.paths_probe import run_paths
from vigilo_probes.seal import seal
from vigilo_probes.store import EvidenceStore, LocalFileEvidenceStore
from vigilo_probes.tls_probe import run_tls
from vigilo_probes.wellknown_probe import run_wellknown

__all__ = [
    "fingerprint",
    "TooManyRedirects",
    "build_pinned_url",
    "run_http",
    "run_probes",
    "run_bundle",
    "run_backend_checks",
    "run_wellknown",
    "run_paths",
    "seal",
    "EvidenceStore",
    "LocalFileEvidenceStore",
    "run_tls",
]
