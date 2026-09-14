"""The Scan Orchestrator's persistence-facing half (docs/modules.md §8): the
state machine and the repository functions `packages/orchestrator/jobs.py`'s
ARQ task bodies drive. Owns `ScanJobRow`/`ScanRow`/`FindingRow` — probing,
check evaluation and scoring arithmetic live in `probes`/`checks`/`scoring`;
this module coordinates them and persists the result.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from vigilo_core.models import Finding, Score, Tier
from vigilo_orchestrator.errors import InvalidScanTransition, ScanJobNotFound
from vigilo_orchestrator.models import Scan, ScanJob
from vigilo_orchestrator.orm import FindingRow, ScanJobRow, ScanRow

# docs/modules.md §8's state machine, verbatim.
_ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "queued": {"authorized", "rejected"},
    "authorized": {"probing"},
    "probing": {"evaluating", "unreachable", "failed"},
    "evaluating": {"scoring", "failed"},
    "scoring": {"reporting"},
    "reporting": {"complete"},
}
TERMINAL_STATUSES = {"complete", "unreachable", "failed", "rejected"}


async def create_scan_job(
    session: AsyncSession,
    target_id: uuid.UUID,
    tier: Tier,
    requested_by: str | None,
    registry_version: str,
    budget: dict | None = None,
) -> ScanJob:
    row = ScanJobRow(
        target_id=target_id,
        tier=tier.value,
        requested_by=requested_by,
        registry_version=registry_version,
        status="queued",
        budget=budget,
    )
    session.add(row)
    await session.flush()
    return ScanJob.model_validate(row)


async def get_scan_job(session: AsyncSession, scan_job_id: uuid.UUID) -> ScanJob | None:
    row = await session.get(ScanJobRow, scan_job_id)
    return ScanJob.model_validate(row) if row else None


async def advance(session: AsyncSession, scan_job_id: uuid.UUID, new_status: str) -> ScanJob:
    row = await session.get(ScanJobRow, scan_job_id)
    if row is None:
        raise ScanJobNotFound("scan job not found", scan_job_id=str(scan_job_id))

    allowed = _ALLOWED_TRANSITIONS.get(row.status, set())
    if new_status not in allowed:
        raise InvalidScanTransition(
            "illegal scan job state transition",
            scan_job_id=str(scan_job_id),
            current_status=row.status,
            requested_status=new_status,
        )

    now = datetime.now(UTC)
    if new_status == "probing" and row.started_at is None:
        row.started_at = now
    if new_status in TERMINAL_STATUSES:
        row.finished_at = now
    row.status = new_status

    await session.flush()
    return ScanJob.model_validate(row)


async def record_scan_result(
    session: AsyncSession,
    job: ScanJob,
    findings: list[Finding],
    result: Score,
    duration_ms: int,
    bundle_id: str | None = None,
) -> Scan:
    """Persists the `Scan` header plus every `Finding` row. Called once, when
    the job reaches `scoring`, immediately before `advance(..., "reporting")`.
    """
    scan_row = ScanRow(
        job_id=job.id,
        target_id=job.target_id,
        registry_version=result.registry_version,
        score=result.value,
        grade=result.grade,
        counts_by_severity={k.value: v for k, v in result.counts_by_severity.items()},
        duration_ms=duration_ms,
        tier=job.tier.value,
        bundle_id=bundle_id,
    )
    session.add(scan_row)
    await session.flush()

    for finding in findings:
        evidence = finding.evidence
        session.add(
            FindingRow(
                scan_id=scan_row.id,
                check_id=finding.check_id,
                status=finding.verdict.value,
                severity=finding.severity.value,
                confidence=finding.confidence.value,
                title=finding.title,
                summary=finding.summary,
                evidence_id=evidence.id if evidence else None,
                fingerprint=finding.fingerprint,
                matched_indicator=evidence.matched_indicator if evidence else None,
                request_summary=evidence.request_summary if evidence else None,
                redaction_applied=evidence.redaction_applied if evidence else None,
            )
        )
    await session.flush()

    return Scan.model_validate(scan_row)


async def get_scan_by_job_id(session: AsyncSession, job_id: uuid.UUID) -> Scan | None:
    result = await session.execute(select(ScanRow).where(ScanRow.job_id == job_id))
    row = result.scalar_one_or_none()
    return Scan.model_validate(row) if row else None


async def get_scan(session: AsyncSession, scan_id: uuid.UUID) -> Scan | None:
    row = await session.get(ScanRow, scan_id)
    return Scan.model_validate(row) if row else None


__all__ = [
    "TERMINAL_STATUSES",
    "create_scan_job",
    "get_scan_job",
    "advance",
    "record_scan_result",
    "get_scan_by_job_id",
    "get_scan",
]
