"""Shared `vigilo_reporting.build_report()` glue for `routers/reports.py` and
`routers/share_links.py` — both need to turn a persisted `Scan` + its
findings into the same `ScanReportResponse` shape.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from vigilo_api.schemas import ScanReportResponse
from vigilo_checks import REGISTRY
from vigilo_core.models import Finding, Score
from vigilo_orchestrator.models import Scan
from vigilo_orchestrator.remediation import get_remediations_for_findings
from vigilo_reporting import build_report

MANIFESTS_BY_CHECK_ID = {check.manifest.check_id: check.manifest for check in REGISTRY}


async def render_scan_report(
    session: AsyncSession, target_origin: str, scan: Scan, findings: list[Finding]
) -> ScanReportResponse:
    score = Score(
        value=scan.score,
        grade=scan.grade,
        registry_version=scan.registry_version,
        counts_by_severity=scan.counts_by_severity,
    )
    # Reads whatever generate_remediations_job has already cached — never
    # calls the LLM itself, so a report render stays fast and available
    # regardless of provider latency (docs/adr/ADR-0004-llm-boundary.md).
    remediations = await get_remediations_for_findings(session, findings, scan.registry_version)
    document = build_report(
        target_origin, score, findings, MANIFESTS_BY_CHECK_ID, scan.created_at, remediations
    )
    # `document.findings` are `vigilo_reporting.models.ReportFinding` instances,
    # a distinct class from this app's own `ReportFindingResponse` even though
    # the fields match — Pydantic v2 requires an exact instance or a dict for
    # a nested model field, so re-validate through dicts rather than passing
    # the reporting package's model objects directly.
    return ScanReportResponse(
        target_origin=document.target_origin,
        registry_version=document.registry_version,
        score=document.score.value,
        grade=document.score.grade,
        counts_by_severity=document.score.counts_by_severity,
        generated_at=document.generated_at,
        findings=[finding.model_dump() for finding in document.findings],
    )
