"""The public REST API (`/public/v1/*`, Phase 9) — key-authenticated,
scoped, rate-limited, deliberately distinct from the session-authenticated
surface above (vision doc §12: "REST, key-authenticated, scoped... distinct
from this session-authenticated one"). Every route's account comes from
`require_scope()` (`api_key_auth.py`), never a Clerk session — the caller
is always a known, existing account, so `POST /scans` reuses the exact
authorization/quota machinery `submit_scan()` established, minus that
endpoint's anonymous-email branch (there is no anonymous path here by
construction — an API key always belongs to somebody).

Every resource lookup here also checks account ownership before returning
anything, unlike some of the session-authenticated routes above (`GET
/v1/scans/{id}` is deliberately public there, an unguessable-UUID share
link by design) — a key-scoped API should never let one caller enumerate
another account's resources by guessing an id.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from vigilo_api.api_key_auth import require_scope
from vigilo_api.deps import QueueDep, SessionDep
from vigilo_api.report_rendering import get_branding_for_target, render_scan_report
from vigilo_api.routers.scans import _DENYLIST, REGISTRY_VERSION
from vigilo_api.schemas import (
    MonitorCreate,
    MonitorResponse,
    ProjectResponse,
    PublicScanSubmission,
    ReportFindingResponse,
    ScanReportResponse,
    ScanStatusResponse,
    ScanSubmissionResponse,
    ScoreHistoryEntry,
)
from vigilo_billing import Meter, QuotaExceeded, consume, entitlements
from vigilo_core.models import Tier
from vigilo_core.validation import ValidationError, validate_target_url
from vigilo_identity.models import Account
from vigilo_monitoring import (
    count_monitors_for_account,
    create_monitor,
    get_monitor,
    get_monitor_by_target,
)
from vigilo_monitoring import disable_monitor as disable_monitor_row
from vigilo_orchestrator.reports import get_findings_for_scan
from vigilo_orchestrator.service import (
    TERMINAL_STATUSES,
    advance,
    count_scan_jobs_for_targets,
    create_scan_job,
    get_scan_by_job_id,
    get_scan_job,
    list_scans_for_target,
)
from vigilo_project.repository import (
    count_targets_for_project,
    create_target,
    get_or_create_default_project,
    get_target,
    get_target_by_origin,
    has_valid_ownership_proof,
    list_target_ids_for_project,
)
from vigilo_security.audit import AuditEvent, audit
from vigilo_security.authorization import AuthorizationRequest, resolve_authorization

ScanRunDep = Annotated[Account, require_scope("scan:run")]
ScanReadDep = Annotated[Account, require_scope("scan:read")]
ReportReadDep = Annotated[Account, require_scope("report:read")]
ProjectReadDep = Annotated[Account, require_scope("project:read")]
MonitorReadDep = Annotated[Account, require_scope("monitor:read")]
MonitorWriteDep = Annotated[Account, require_scope("monitor:write")]

_SCANS_MONTHLY_WINDOW = timedelta(days=30)
_STREAM_POLL_SECONDS = 1.0
_STREAM_MAX_SECONDS = 120.0

router = APIRouter(prefix="/public/v1", tags=["public-api"])


async def _owned_target(session: SessionDep, account: Account, target_id: uuid.UUID):
    target = await get_target(session, target_id)
    project = await get_or_create_default_project(session, account.id)
    if target is None or target.project_id != project.id:
        raise HTTPException(status_code=404, detail="target not found")
    return target


async def _owned_scan_job(session: SessionDep, account: Account, scan_job_id: uuid.UUID):
    job = await get_scan_job(session, scan_job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="scan not found")
    await _owned_target(session, account, job.target_id)
    return job


@router.post("/scans", status_code=202, response_model=ScanSubmissionResponse)
async def public_submit_scan(
    body: PublicScanSubmission,
    session: SessionDep,
    queue: QueueDep,
    account: ScanRunDep,
) -> ScanSubmissionResponse:
    try:
        origin = validate_target_url(body.target_url)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.message) from exc

    project = await get_or_create_default_project(session, account.id)
    existing_target = await get_target_by_origin(session, project.id, origin)
    target_verification_status = (
        existing_target.verification_status if existing_target else Tier.PASSIVE
    )
    ownership_proof_valid = (
        await has_valid_ownership_proof(session, existing_target.id) if existing_target else False
    )
    plan = entitlements(account.plan_id)

    decision = resolve_authorization(
        AuthorizationRequest(
            target_origin=origin,
            requested_tier=body.requested_tier,
            target_verification_status=target_verification_status,
            target_opt_out=False,
            ownership_proof_valid=ownership_proof_valid,
            recent_scan_count_24h=0,
            denylisted=False,
            active_tier_permitted_by_plan=plan.active_tier_allowed,
        )
    )

    if not decision.allowed:
        await audit(
            session,
            AuditEvent(
                actor="public_api",
                action="scan_denied",
                subject=origin,
                account_id=account.id,
                metadata={"reason": decision.reason},
            ),
        )
        await session.commit()
        raise HTTPException(status_code=403, detail=decision.reason)

    if existing_target is None:
        target_count = await count_targets_for_project(session, project.id)
        target_decision = consume(target_count, 1, Meter.TARGETS, plan)
        if not target_decision.allowed:
            await session.commit()
            raise QuotaExceeded(
                "targets limit reached for plan",
                limit=target_decision.limit,
                current=target_decision.current,
            )

    target_ids = await list_target_ids_for_project(session, project.id)
    since = datetime.now(UTC) - _SCANS_MONTHLY_WINDOW
    scan_count = await count_scan_jobs_for_targets(session, target_ids, since)
    scans_decision = consume(scan_count, 1, Meter.SCANS_MONTHLY, plan)
    if not scans_decision.allowed:
        await session.commit()
        raise QuotaExceeded(
            "scans-per-month limit reached for plan",
            limit=scans_decision.limit,
            current=scans_decision.current,
        )

    target = await create_target(session, project.id, origin)
    await audit(
        session,
        AuditEvent(
            actor="public_api",
            action="scan_authorized",
            subject=origin,
            account_id=account.id,
            metadata={"granted_tier": decision.granted_tier.value},
        ),
    )
    job = await create_scan_job(
        session, target.id, decision.granted_tier, account.email, REGISTRY_VERSION
    )
    job = await advance(session, job.id, "authorized")
    await session.commit()

    await queue.enqueue_job("run_scan_job", str(job.id))
    return ScanSubmissionResponse(scan_job_id=job.id, status=job.status, granted_tier=job.tier)


@router.get("/scans/{scan_job_id}", response_model=ScanStatusResponse)
async def public_get_scan_status(
    scan_job_id: uuid.UUID, session: SessionDep, account: ScanReadDep
) -> ScanStatusResponse:
    job = await _owned_scan_job(session, account, scan_job_id)
    target = await get_target(session, job.target_id)
    scan = await get_scan_by_job_id(session, scan_job_id)

    return ScanStatusResponse(
        scan_job_id=job.id,
        status=job.status,
        target_origin=target.origin if target else "",
        tier=job.tier,
        score=scan.score if scan else None,
        grade=scan.grade if scan else None,
        counts_by_severity=scan.counts_by_severity if scan else None,
        finished_at=job.finished_at,
    )


async def scan_status_events(
    session: SessionDep,
    scan_job_id: uuid.UUID,
    poll_seconds: float,
    max_seconds: float,
):
    """The SSE generator, extracted as its own named, directly-testable
    function — a plain unit test can exhaust it without going through the
    ASGI/HTTP layer, which (at least with httpx's `ASGITransport`) buffers
    a streaming response until the generator finishes rather than yielding
    incrementally, making `max_seconds`/`poll_seconds` the only levers a
    real HTTP-level test has to keep itself fast."""
    last_status: str | None = None
    elapsed = 0.0
    while elapsed < max_seconds:
        job = await get_scan_job(session, scan_job_id)
        if job is None:
            break
        if job.status != last_status:
            last_status = job.status
            yield f"data: {json.dumps({'status': job.status})}\n\n"
        if job.status in TERMINAL_STATUSES:
            break
        await asyncio.sleep(poll_seconds)
        elapsed += poll_seconds


@router.get("/scans/{scan_job_id}/stream")
async def public_stream_scan_status(
    scan_job_id: uuid.UUID, session: SessionDep, account: ScanReadDep
) -> StreamingResponse:
    await _owned_scan_job(session, account, scan_job_id)
    return StreamingResponse(
        scan_status_events(session, scan_job_id, _STREAM_POLL_SECONDS, _STREAM_MAX_SECONDS),
        media_type="text/event-stream",
    )


@router.get("/scans/{scan_job_id}/report", response_model=ScanReportResponse)
async def public_get_scan_report(
    scan_job_id: uuid.UUID, session: SessionDep, account: ReportReadDep
) -> ScanReportResponse:
    job = await _owned_scan_job(session, account, scan_job_id)
    scan = await get_scan_by_job_id(session, scan_job_id)
    if scan is None:
        raise HTTPException(status_code=409, detail="report not ready")

    target = await get_target(session, job.target_id)
    findings = await get_findings_for_scan(session, scan.id)
    response = await render_scan_report(session, target.origin if target else "", scan, findings)
    response.scan_job_id = scan_job_id
    response.target_id = job.target_id
    response.is_owner = True
    response.branding = await get_branding_for_target(session, job.target_id)
    return response


@router.get("/scans/{scan_job_id}/findings", response_model=list[ReportFindingResponse])
async def public_get_scan_findings(
    scan_job_id: uuid.UUID, session: SessionDep, account: ReportReadDep
) -> list[ReportFindingResponse]:
    report = await public_get_scan_report(scan_job_id, session, account)
    return report.findings


@router.get("/targets/{target_id}/scores", response_model=list[ScoreHistoryEntry])
async def public_get_target_scores(
    target_id: uuid.UUID, session: SessionDep, account: ReportReadDep
) -> list[ScoreHistoryEntry]:
    target = await _owned_target(session, account, target_id)
    scans = await list_scans_for_target(session, target.id)
    return [
        ScoreHistoryEntry(
            scan_id=scan.id,
            score=scan.score,
            grade=scan.grade,
            registry_version=scan.registry_version,
            created_at=scan.created_at,
        )
        for scan in scans
    ]


@router.get("/projects", response_model=list[ProjectResponse])
async def public_list_projects(
    session: SessionDep, account: ProjectReadDep
) -> list[ProjectResponse]:
    project = await get_or_create_default_project(session, account.id)
    return [
        ProjectResponse(project_id=project.id, name=project.name, created_at=project.created_at)
    ]


def _to_monitor_response(monitor) -> MonitorResponse:
    return MonitorResponse(
        monitor_id=monitor.id,
        target_id=monitor.target_id,
        cadence_hours=monitor.cadence_hours,
        enabled=monitor.enabled,
        next_run_at=monitor.next_run_at,
        quiet_start_utc=monitor.quiet_start_utc,
        quiet_end_utc=monitor.quiet_end_utc,
    )


@router.post("/targets/{target_id}/monitors", status_code=201, response_model=MonitorResponse)
async def public_create_target_monitor(
    target_id: uuid.UUID,
    body: MonitorCreate,
    session: SessionDep,
    account: MonitorWriteDep,
) -> MonitorResponse:
    target = await _owned_target(session, account, target_id)
    plan = entitlements(account.plan_id)

    if plan.monitoring_frequency is None:
        raise QuotaExceeded("monitoring is not included in the account's plan")
    if plan.monitoring_frequency == "weekly" and body.cadence_hours != 168:
        raise HTTPException(status_code=422, detail="this plan only supports a weekly cadence")
    if plan.monitoring_frequency == "daily+custom" and not (1 <= body.cadence_hours <= 168):
        raise HTTPException(status_code=422, detail="cadence_hours must be between 1 and 168")

    if await get_monitor_by_target(session, target.id) is None:
        current_count = await count_monitors_for_account(session, account.id)
        decision = consume(current_count, 1, Meter.MONITORS, plan)
        if not decision.allowed:
            raise QuotaExceeded(
                "monitors limit reached for plan", limit=decision.limit, current=decision.current
            )

    monitor = await create_monitor(
        session,
        target_id=target.id,
        account_id=account.id,
        cadence_hours=body.cadence_hours,
        next_run_at=datetime.now(UTC),
        quiet_start_utc=body.quiet_start_utc,
        quiet_end_utc=body.quiet_end_utc,
    )
    return _to_monitor_response(monitor)


@router.get("/targets/{target_id}/monitors", response_model=MonitorResponse)
async def public_get_target_monitor(
    target_id: uuid.UUID, session: SessionDep, account: MonitorReadDep
) -> MonitorResponse:
    target = await _owned_target(session, account, target_id)
    monitor = await get_monitor_by_target(session, target.id)
    if monitor is None:
        raise HTTPException(status_code=404, detail="no monitor for this target")
    return _to_monitor_response(monitor)


@router.post("/monitors/{monitor_id}/disable", response_model=MonitorResponse)
async def public_disable_monitor(
    monitor_id: uuid.UUID, session: SessionDep, account: MonitorWriteDep
) -> MonitorResponse:
    existing = await get_monitor(session, monitor_id)
    if existing is None or existing.account_id != account.id:
        raise HTTPException(status_code=404, detail="monitor not found")

    monitor = await disable_monitor_row(session, monitor_id)
    if monitor is None:
        raise HTTPException(status_code=404, detail="monitor not found")
    return _to_monitor_response(monitor)
