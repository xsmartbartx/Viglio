"""Vigilo reporting: render findings for humans (docs/modules.md §6).

Phase 4 scope: deterministic HTML report data (`build_report`), PDF export
(`render_pdf`), and a pure badge renderer (`render_badge`) — all built on
each check's static `remediation_template`, no LLM call. Phase 5 swaps
`generate_remediation`'s internals for a Claude call without changing this
module's public surface.

Every function here is pure and depends on `core` only — no `persistence`,
no `checks` — the caller fetches Scan/Finding rows and check manifests and
passes them in. This is a deliberate, documented deviation from
`docs/modules.md` §6's literal `build_report(scan_id) -> Report` sketch,
matching the precedent Phase 3 set for `resolve_authorization`.
"""

from __future__ import annotations

from vigilo_reporting.badge import render_badge
from vigilo_reporting.builder import build_report
from vigilo_reporting.errors import PdfRenderError
from vigilo_reporting.models import EvidenceView, ReportDocument, ReportFinding, RemediationPrompt
from vigilo_reporting.pdf import render_pdf
from vigilo_reporting.remediation import generate_remediation

__all__ = [
    "ReportDocument",
    "ReportFinding",
    "EvidenceView",
    "RemediationPrompt",
    "build_report",
    "generate_remediation",
    "render_pdf",
    "render_badge",
    "PdfRenderError",
]
