"""Monitoring's ARQ job bodies (docs/build-roadmap.md's Phase 8): the
scheduler cron job, the post-scan diff job, and the scan-failure alert
job. These live here, in the app, rather than in `packages/orchestrator/
jobs.py` alongside the other job bodies, because `packages/monitoring`
depends on `packages/orchestrator` (docs/modules.md §9) — orchestrator
importing monitoring back would be a cycle. `packages/orchestrator`'s own
job bodies only ever reference these by ARQ's string-based `enqueue_job`,
never by Python import, so the dependency graph stays one-directional; an
app is always a leaf in that graph and is free to depend on both.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from vigilo_billing import entitlements
from vigilo_core.logging import LogEvent, log
from vigilo_core.logging import Severity as LogSeverity
from vigilo_core.models import Tier
from vigilo_identity.repository import get_account_by_id
from vigilo_monitoring import (
    Monitor,
    compute_next_run_at,
    detect_regression,
    disable_monitor,
    due_monitors,
    get_monitor_by_target,
    mark_alert_sent,
    record_alert,
    reschedule_monitor,
)
from vigilo_notification import AlertOccurrence, NotificationEvent, notify
from vigilo_orchestrator.service import (
    advance,
    create_scan_job,
    get_failed_findings_for_scan,
    get_scan_by_job_id,
    get_scan_job,
    list_ever_failed_fingerprints_before,
    list_scans_for_target,
)
from vigilo_persistence import session_scope
from vigilo_project.repository import get_target, has_valid_ownership_proof
from vigilo_security.audit import AuditEvent, audit
from vigilo_security.authorization import AuthorizationRequest, resolve_authorization

REGISTRY_VERSION = "0.1"  # small, deliberate duplication of scans.py's own
_MODULE = "vigilo_scanner"


async def check_due_monitors_job(ctx: dict[str, Any]) -> None:
    now = datetime.now(UTC)
    async with session_scope() as session:
        monitors = await due_monitors(session, now)

    for monitor in monitors:
        await _run_due_monitor(ctx, monitor, now)


async def _run_due_monitor(ctx: dict[str, Any], monitor: Monitor, now: datetime) -> None:
    job_id: uuid.UUID | None = None

    async with session_scope() as session:
        target = await get_target(session, monitor.target_id)
        account = await get_account_by_id(session, monitor.account_id)
        if target is None or account is None:
            return

        ownership_proof_valid = await has_valid_ownership_proof(session, target.id)
        plan = entitlements(account.plan_id)

        # Always request ACTIVE — resolve_authorization() downgrades to
        # passive on its own if the proof has since lapsed or the plan no
        # longer includes active tier, the same mechanism submit_scan()
        # uses. This is what "re-verifies ownership before every
        # active-tier run and downgrades to passive if verification has
        # lapsed" (vision §10.1) actually means in code.
        decision = resolve_authorization(
            AuthorizationRequest(
                target_origin=target.origin,
                requested_tier=Tier.ACTIVE,
                target_verification_status=target.verification_status,
                target_opt_out=target.opt_out_flag,
                ownership_proof_valid=ownership_proof_valid,
                recent_scan_count_24h=0,
                denylisted=False,  # no real denylist source yet, matching scans.py's own stub
                active_tier_permitted_by_plan=plan.active_tier_allowed,
            )
        )

        if not decision.allowed:
            # Opted out or denylisted since the monitor was created — stop
            # scheduling it rather than repeatedly failing every cycle.
            await disable_monitor(session, monitor.id)
            await audit(
                session,
                AuditEvent(
                    actor="monitoring",
                    action="monitor_disabled",
                    subject=target.origin,
                    account_id=account.id,
                    metadata={"reason": decision.reason},
                ),
            )
            await session.commit()
            return

        job = await create_scan_job(
            session, target.id, decision.granted_tier, account.email, REGISTRY_VERSION
        )
        job = await advance(session, job.id, "authorized")
        job_id = job.id

        next_run_at = compute_next_run_at(
            monitor.cadence_hours, monitor.quiet_start_utc, monitor.quiet_end_utc, now
        )
        await reschedule_monitor(session, monitor.id, next_run_at, monitor.pending_score_drop)
        await audit(
            session,
            AuditEvent(
                actor="monitoring",
                action="monitor_scan_authorized",
                subject=target.origin,
                account_id=account.id,
                metadata={"granted_tier": decision.granted_tier.value},
            ),
        )
        await session.commit()

    redis = ctx.get("redis")
    if redis is not None and job_id is not None:
        await redis.enqueue_job("run_scan_job", str(job_id))


async def detect_regression_job(ctx: dict[str, Any], scan_job_id: str) -> None:
    """Always enqueued from `run_scan_job` right after scoring
    (`packages/orchestrator/jobs.py`) — returns immediately if the scan's
    target has no active monitor, matching `generate_remediations_job`'s
    own `if not failed: return` precedent."""
    async with session_scope() as session:
        scan = await get_scan_by_job_id(session, uuid.UUID(scan_job_id))
        if scan is None:
            return

        monitor = await get_monitor_by_target(session, scan.target_id)
        if monitor is None or not monitor.enabled:
            return

        recent_scans = await list_scans_for_target(session, scan.target_id, limit=2)
        if len(recent_scans) < 2:
            return  # first scan ever under this monitor — nothing to diff against

        current_scan, previous_scan = recent_scans[0], recent_scans[1]

        current_failed = await get_failed_findings_for_scan(session, current_scan.id)
        previous_failed = await get_failed_findings_for_scan(session, previous_scan.id)
        ever_failed_before_previous = await list_ever_failed_fingerprints_before(
            session, scan.target_id, previous_scan.created_at
        )

        report = detect_regression(
            previous_failed=previous_failed,
            current_failed=current_failed,
            ever_failed_before_previous=ever_failed_before_previous,
            previous_registry_version=previous_scan.registry_version,
            current_registry_version=current_scan.registry_version,
            previous_score=previous_scan.score,
            current_score=current_scan.score,
            had_pending_score_drop=monitor.pending_score_drop,
        )

        target = await get_target(session, scan.target_id)
        account = await get_account_by_id(session, monitor.account_id)
        if target is None or account is None:
            return

        alert_ids: list[uuid.UUID] = []
        occurrences: list[AlertOccurrence] = []

        for event in report.events:
            dedupe_key = f"{scan.target_id}:{event.fingerprint}:{event.event_type}"
            alert = await record_alert(
                session,
                monitor_id=monitor.id,
                target_id=scan.target_id,
                scan_id=current_scan.id,
                type=event.event_type,
                dedupe_key=dedupe_key,
                severity=event.severity,
                fingerprint=event.fingerprint,
            )
            alert_ids.append(alert.id)
            occurrences.append(
                AlertOccurrence(
                    event_type=event.event_type,
                    target_id=scan.target_id,
                    target_origin=target.origin,
                    check_id=event.check_id,
                    severity=event.severity,
                )
            )

        if report.score_drop:
            dedupe_key = f"{scan.target_id}:score:score_drop"
            alert = await record_alert(
                session,
                monitor_id=monitor.id,
                target_id=scan.target_id,
                scan_id=current_scan.id,
                type="score_drop",
                dedupe_key=dedupe_key,
            )
            alert_ids.append(alert.id)
            occurrences.append(
                AlertOccurrence(
                    event_type="score_drop", target_id=scan.target_id, target_origin=target.origin
                )
            )

        await reschedule_monitor(
            session, monitor.id, monitor.next_run_at, report.pending_score_drop
        )
        account_email = account.email
        await session.commit()

    if not occurrences:
        return

    event = NotificationEvent(account_email=account_email, occurrences=occurrences)
    result = await notify(event)
    if not result.delivered:
        log(
            LogEvent(
                event="monitoring.alert_email_failed",
                severity=LogSeverity.ERROR,
                module=_MODULE,
                context={"scan_job_id": scan_job_id, "reason": result.reason},
            )
        )
        return

    now = datetime.now(UTC)
    async with session_scope() as session:
        for alert_id in alert_ids:
            await mark_alert_sent(session, alert_id, now)


async def record_scan_failed_alert_job(ctx: dict[str, Any], scan_job_id: str, reason: str) -> None:
    """Enqueued from `run_scan_job`'s three failure/unreachable branches
    (`packages/orchestrator/jobs.py`) — a no-op unless the failed job's
    target has an active monitor. No `Scan` row exists for a failed job,
    so `AlertRow.scan_id` is left `None`."""
    async with session_scope() as session:
        job = await get_scan_job(session, uuid.UUID(scan_job_id))
        if job is None:
            return

        monitor = await get_monitor_by_target(session, job.target_id)
        if monitor is None or not monitor.enabled:
            return

        target = await get_target(session, job.target_id)
        account = await get_account_by_id(session, monitor.account_id)
        if target is None or account is None:
            return

        dedupe_key = f"{job.target_id}:scan_failed:{job.id}"
        alert = await record_alert(
            session,
            monitor_id=monitor.id,
            target_id=job.target_id,
            scan_id=None,
            type="scan_failed",
            dedupe_key=dedupe_key,
        )
        alert_id = alert.id
        account_email = account.email
        target_origin = target.origin
        target_id = target.id
        await session.commit()

    event = NotificationEvent(
        account_email=account_email,
        occurrences=[
            AlertOccurrence(
                event_type="scan_failed",
                target_id=target_id,
                target_origin=target_origin,
                reason=reason,
            )
        ],
    )
    result = await notify(event)
    if result.delivered:
        async with session_scope() as session:
            await mark_alert_sent(session, alert_id, datetime.now(UTC))
