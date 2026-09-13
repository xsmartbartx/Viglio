"""`POST /v1/scans` / `GET /v1/scans/{id}` — the anonymous free-scan path
(exit criterion a). `resolve_authorization()` runs, and the decision is
audited and committed, before anything is enqueued — matching ADR-0003
("written to the audit trail before the scan is queued, not after") and
`docs/architecture.md` §4's sequence diagram.
"""

from __future__ import annotations

import uuid

from arq.connections import ArqRedis
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from vigilo_core.models import Tier
from vigilo_core.validation import ValidationError, validate_target_url
from vigilo_identity.repository import get_or_create_account
from vigilo_project.repository import create_target, get_or_create_default_project, get_target
from vigilo_security.audit import AuditEvent, audit
from vigilo_security.authorization import AuthorizationRequest, resolve_authorization

from vigilo_api.deps import get_queue, get_session
from vigilo_api.schemas import ScanStatusResponse, ScanSubmission, ScanSubmissionResponse
from vigilo_orchestrator.service import advance, create_scan_job, get_scan_by_job_id, get_scan_job

router = APIRouter(prefix="/v1/scans", tags=["scans"])

REGISTRY_VERSION = "0.1"
_DENYLIST: frozenset[str] = frozenset()  # the real denylist source is Phase 6/7


@router.post("", status_code=202, response_model=ScanSubmissionResponse)
async def submit_scan(
    body: ScanSubmission,
    session: AsyncSession = Depends(get_session),
    queue: ArqRedis = Depends(get_queue),
) -> ScanSubmissionResponse:
    try:
        origin = validate_target_url(body.target_url)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.message) from exc

    decision = resolve_authorization(
        AuthorizationRequest(
            target_origin=origin,
            requested_tier=body.requested_tier,
            target_verification_status=Tier.PASSIVE,
            target_opt_out=False,
            ownership_proof_valid=False,
            recent_scan_count_24h=0,
            denylisted=origin in _DENYLIST,
        )
    )

    if not decision.allowed:
        await audit(
            session,
            AuditEvent(actor="api", action="scan_denied", subject=origin, metadata={"reason": decision.reason}),
        )
        await session.commit()  # the denial must survive the HTTPException below
        raise HTTPException(status_code=403, detail=decision.reason)

    account = await get_or_create_account(session, email=body.email)
    project = await get_or_create_default_project(session, account.id)
    target = await create_target(session, project.id, origin)

    await audit(
        session,
        AuditEvent(
            actor="api",
            action="scan_authorized",
            subject=origin,
            account_id=account.id,
            metadata={"granted_tier": decision.granted_tier.value},
        ),
    )

    job = await create_scan_job(session, target.id, decision.granted_tier, body.email, REGISTRY_VERSION)
    job = await advance(session, job.id, "authorized")
    await session.commit()  # the job row must be durable before a worker can see it

    await queue.enqueue_job("run_scan_job", str(job.id))

    return ScanSubmissionResponse(scan_job_id=job.id, status=job.status, granted_tier=job.tier)


@router.get("/{scan_job_id}", response_model=ScanStatusResponse)
async def get_scan_status(
    scan_job_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> ScanStatusResponse:
    job = await get_scan_job(session, scan_job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="scan not found")

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
