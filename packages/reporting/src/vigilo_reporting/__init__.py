"""Vigilo reporting: render findings for humans (docs/modules.md §6).

Deterministic HTML report data (`build_report`), PDF export (`render_pdf`),
and a pure badge renderer (`render_badge`). Phase 5 added Claude-backed
remediation (`generate_remediation`) alongside the always-available,
deterministic fallback (`template_remediation`) —
docs/adr/ADR-0004-llm-boundary.md is the binding rule set: `build_report()`
only ever calls `template_remediation()` directly, never
`generate_remediation()`, so a report render never depends on LLM
availability or latency.

Every function here depends on `core` and (as of Phase 5)
`integrations` only — no `persistence`, no `checks` — the caller fetches
Scan/Finding rows and check manifests and passes them in. This is a
deliberate, documented deviation from `docs/modules.md` §6's literal
`build_report(scan_id) -> Report` sketch, matching the precedent Phase 3 set
for `resolve_authorization`.
"""

from __future__ import annotations

from vigilo_reporting.badge import render_badge
from vigilo_reporting.builder import build_report
from vigilo_reporting.errors import PdfRenderError
from vigilo_reporting.models import (
    EvidenceView,
    RemediationPrompt,
    RemediationView,
    ReportDocument,
    ReportFinding,
)
from vigilo_reporting.pdf import render_pdf
from vigilo_reporting.remediation import generate_remediation, template_remediation
from vigilo_reporting.sarif import build_sarif_report

__all__ = [
    "ReportDocument",
    "ReportFinding",
    "EvidenceView",
    "RemediationPrompt",
    "RemediationView",
    "build_report",
    "build_sarif_report",
    "generate_remediation",
    "template_remediation",
    "render_pdf",
    "render_badge",
    "PdfRenderError",
]
