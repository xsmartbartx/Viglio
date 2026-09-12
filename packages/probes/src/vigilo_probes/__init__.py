"""Vigilo probes: collect evidence about a target. This is the only module
permitted to make outbound requests to a target (docs/modules.md §3).

A probe records what happened; it never interprets, never assigns severity,
never imports `vigilo_checks`. It cannot decide its own request budget — that
governance belongs to the Scan Orchestrator (Phase 3).
"""

from vigilo_probes.fingerprint import fingerprint
from vigilo_probes.http_probe import TooManyRedirects, run_http
from vigilo_probes.orchestrator import run_probes
from vigilo_probes.seal import seal
from vigilo_probes.store import EvidenceStore, LocalFileEvidenceStore
from vigilo_probes.tls_probe import run_tls

__all__ = [
    "fingerprint",
    "TooManyRedirects",
    "run_http",
    "run_probes",
    "seal",
    "EvidenceStore",
    "LocalFileEvidenceStore",
    "run_tls",
]
