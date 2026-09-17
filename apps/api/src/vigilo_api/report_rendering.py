"""Shared `vigilo_reporting.build_report()` glue for `routers/reports.py` and
`routers/share_links.py` — both need to turn a persisted `Scan` + its
findings into the same `ScanReportResponse` shape.
"""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from vigilo_api.schemas import BrandingProfileResponse, ScanReportResponse
from vigilo_billing import entitlements
from vigilo_checks import REGISTRY
from vigilo_core.models import Finding, Score
from vigilo_identity.repository import get_account_by_id, get_branding_profile
from vigilo_orchestrator.models import Scan
from vigilo_orchestrator.remediation import get_remediations_for_findings
from vigilo_project.repository import get_project, get_target
from vigilo_reporting import build_report

MANIFESTS_BY_CHECK_ID = {check.manifest.check_id: check.manifest for check in REGISTRY}


async def get_branding_for_target(
    session: AsyncSession, target_id: uuid.UUID
) -> BrandingProfileResponse | None:
    """`None` whenever the target's owning account isn't on a
    `white_label_allowed` plan or hasn't configured a profile — so
    `apps/web` can render its own default styling unconditionally in that
    case, never needing to check the plan itself (Phase 9)."""
    target = await get_target(session, target_id)
    if target is None:
        return None
    project = await get_project(session, target.project_id)
    if project is None:
        return None
    account = await get_account_by_id(session, project.account_id)
    if account is None or not entitlements(account.plan_id).white_label_allowed:
        return None

    profile = await get_branding_profile(session, account.id)
    if profile is None:
        return None

    return BrandingProfileResponse(
        logo_url=profile.logo_url,
        primary_color=profile.primary_color,
        footer_text=profile.footer_text,
        custom_domain=profile.custom_domain,
    )


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
