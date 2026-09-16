"""`POST`/`GET /v1/targets/{target_id}/monitors`, `POST
/v1/monitors/{monitor_id}/disable`, `GET /v1/targets/{target_id}/scores`,
`GET /v1/targets/{target_id}/alerts` (Phase 8). Scheduling itself
(`check_due_monitors_job`) and diffing (`detect_regression_job`) run in
`apps/scanner`'s worker, never here — this router only ever creates or
reads the `Monitor`/`Alert` rows those jobs act on.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException

from vigilo_api.deps import AccountDep, SessionDep
from vigilo_api.schemas import AlertResponse, MonitorCreate, MonitorResponse, ScoreHistoryEntry
from vigilo_billing import Meter, QuotaExceeded, consume, entitlements
from vigilo_identity.models import Account
from vigilo_monitoring import (
    count_monitors_for_account,
    create_monitor,
    get_monitor,
    get_monitor_by_target,
    list_alerts_for_target,
)
from vigilo_monitoring import disable_monitor as disable_monitor_row
from vigilo_orchestrator.service import list_scans_for_target
from vigilo_project.repository import get_or_create_default_project, get_target

router = APIRouter(tags=["monitors"])


def _to_response(monitor) -> MonitorResponse:
    return MonitorResponse(
        monitor_id=monitor.id,
        target_id=monitor.target_id,
        cadence_hours=monitor.cadence_hours,
        enabled=monitor.enabled,
        next_run_at=monitor.next_run_at,
        quiet_start_utc=monitor.quiet_start_utc,
        quiet_end_utc=monitor.quiet_end_utc,
    )


async def _owned_target_or_404(session: SessionDep, account: Account, target_id: uuid.UUID):
    target = await get_target(session, target_id)
    project = await get_or_create_default_project(session, account.id)
    if target is None or target.project_id != project.id:
        raise HTTPException(status_code=404, detail="target not found")
    return target


def _validate_cadence(cadence_hours: int, monitoring_frequency: str | None) -> None:
    if monitoring_frequency is None:
        raise QuotaExceeded("monitoring is not included in the account's plan")
    if monitoring_frequency == "weekly" and cadence_hours != 168:
        raise HTTPException(
            status_code=422, detail="this plan only supports a fixed weekly (168h) cadence"
        )
    if monitoring_frequency == "daily+custom" and not (1 <= cadence_hours <= 168):
        raise HTTPException(status_code=422, detail="cadence_hours must be between 1 and 168")


@router.post("/v1/targets/{target_id}/monitors", status_code=201, response_model=MonitorResponse)
async def create_target_monitor(
    target_id: uuid.UUID,
    body: MonitorCreate,
    account: AccountDep,
    session: SessionDep,
) -> MonitorResponse:
    target = await _owned_target_or_404(session, account, target_id)
    plan = entitlements(account.plan_id)
    _validate_cadence(body.cadence_hours, plan.monitoring_frequency)

    # A genuinely new monitor consumes the MONITORS quota; re-enabling or
    # re-configuring an existing one (create_monitor is idempotent by
    # target) does not — matches POST /v1/targets' own
    # only-count-if-new precedent.
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
    return _to_response(monitor)


@router.get("/v1/targets/{target_id}/monitors", response_model=MonitorResponse)
async def get_target_monitor(
    target_id: uuid.UUID, account: AccountDep, session: SessionDep
) -> MonitorResponse:
    target = await _owned_target_or_404(session, account, target_id)
    monitor = await get_monitor_by_target(session, target.id)
    if monitor is None:
        raise HTTPException(status_code=404, detail="no monitor for this target")
    return _to_response(monitor)


@router.post("/v1/monitors/{monitor_id}/disable", response_model=MonitorResponse)
async def disable_target_monitor(
    monitor_id: uuid.UUID, account: AccountDep, session: SessionDep
) -> MonitorResponse:
    monitor = await disable_monitor_row(session, monitor_id)
    if monitor is None or monitor.account_id != account.id:
        raise HTTPException(status_code=404, detail="monitor not found")
    return _to_response(monitor)


@router.get("/v1/targets/{target_id}/scores", response_model=list[ScoreHistoryEntry])
async def get_target_score_history(
    target_id: uuid.UUID, account: AccountDep, session: SessionDep
) -> list[ScoreHistoryEntry]:
    target = await _owned_target_or_404(session, account, target_id)
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


@router.get("/v1/targets/{target_id}/alerts", response_model=list[AlertResponse])
async def get_target_alerts(
    target_id: uuid.UUID, account: AccountDep, session: SessionDep
) -> list[AlertResponse]:
    target = await _owned_target_or_404(session, account, target_id)
    alerts = await list_alerts_for_target(session, target.id)
    return [
        AlertResponse(
            alert_id=alert.id,
            type=alert.type,
            severity=alert.severity,
            fingerprint=alert.fingerprint,
            sent_at=alert.sent_at,
            created_at=alert.created_at,
        )
        for alert in alerts
    ]
