"""Vigilo orchestrator: owns the lifecycle of a scan — plan, enqueue, track,
assemble, finalise (docs/modules.md §8).

Deliberately does NOT import `vigilo_orchestrator.jobs` here — that module
imports `vigilo_probes`, and this package's `__init__.py` is what every
consumer (including `apps/api`) actually loads on `import
vigilo_orchestrator.<anything>`. `apps/scanner`'s worker (the one process
allowed to run scan jobs) imports `vigilo_orchestrator.jobs` directly,
never through this package root — found and fixed in Phase 4: before this,
`apps/api` transitively loaded `vigilo_probes` into its own process despite
`test_no_egress_imports.py`'s AST check passing, because that check only
scans `apps/api`'s own source files, not the runtime import graph.
"""

from __future__ import annotations

from vigilo_orchestrator.errors import (
    InvalidScanTransition,
    ReportNotFound,
    ScanJobNotFound,
    ShareLinkNotFound,
)
from vigilo_orchestrator.models import Report, Scan, ScanJob, ShareLink
from vigilo_orchestrator.reports import (
    create_share_link,
    get_findings_for_scan,
    get_or_create_html_report,
    get_or_create_pdf_report,
    get_report,
    get_report_pdf_bytes,
    get_share_link,
    list_share_links,
    mark_report_complete,
    mark_report_failed,
    record_share_link_view,
    resolve_share_link,
    revoke_share_link,
)
from vigilo_orchestrator.service import (
    advance,
    create_scan_job,
    get_scan_by_job_id,
    get_scan_job,
    record_scan_result,
)

__all__ = [
    "ScanJob",
    "Scan",
    "Report",
    "ShareLink",
    "ScanJobNotFound",
    "InvalidScanTransition",
    "ReportNotFound",
    "ShareLinkNotFound",
    "create_scan_job",
    "get_scan_job",
    "advance",
    "record_scan_result",
    "get_scan_by_job_id",
    "get_findings_for_scan",
    "get_or_create_html_report",
    "get_or_create_pdf_report",
    "get_report",
    "get_report_pdf_bytes",
    "mark_report_complete",
    "mark_report_failed",
    "create_share_link",
    "list_share_links",
    "get_share_link",
    "revoke_share_link",
    "resolve_share_link",
    "record_share_link_view",
]
