from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

import vigilo_scanner.jobs as jobs
from vigilo_core.models import Confidence, Finding, Score, Severity, Tier, Verdict
from vigilo_identity.repository import get_or_create_account
from vigilo_monitoring.orm import AlertRow
from vigilo_monitoring.repository import create_monitor, get_monitor_by_target
from vigilo_orchestrator.service import advance, create_scan_job, record_scan_result
from vigilo_persistence import session_scope
from vigilo_project.repository import create_target, get_or_create_default_project, set_opt_out


class _FakeRedis:
    def __init__(self) -> None:
        self.enqueued: list[tuple[str, tuple]] = []

    async def enqueue_job(self, function: str, *args) -> None:
        self.enqueued.append((function, args))


async def _seed_target(email: str) -> tuple[uuid.UUID, uuid.UUID]:
    async with session_scope() as session:
        account = await get_or_create_account(session, email=email)
        project = await get_or_create_default_project(session, account.id)
        target = await create_target(session, project.id, "https://example.com")
        return account.id, target.id


async def _seed_scan(
    target_id: uuid.UUID, findings: list[Finding], score: float, requested_by: str
):
    async with session_scope() as session:
        job = await create_scan_job(session, target_id, Tier.PASSIVE, requested_by, "0.1")
        job = await advance(session, job.id, "authorized")
        job = await advance(session, job.id, "probing")
        job = await advance(session, job.id, "evaluating")
        result = Score(value=score, grade="A", registry_version="0.1")
        return await record_scan_result(session, job, findings, result, duration_ms=10)


def _finding(fingerprint: str, check_id: str = "VG-HDR-001") -> Finding:
    return Finding(
        check_id=check_id,
        verdict=Verdict.FAILED,
        severity=Severity.CRITICAL,
        confidence=Confidence.CONFIRMED,
        title="a failed check",
        summary="failed",
        fingerprint=fingerprint,
    )


async def test_check_due_monitors_job_creates_and_enqueues_a_scan(db_schema) -> None:
    account_id, target_id = await _seed_target("due-monitor@example.com")
    now = datetime.now(UTC)
    async with session_scope() as session:
        await create_monitor(
            session, target_id, account_id, cadence_hours=24, next_run_at=now - timedelta(minutes=1)
        )

    redis = _FakeRedis()
    await jobs.check_due_monitors_job({"redis": redis})

    assert len(redis.enqueued) == 1
    assert redis.enqueued[0][0] == "run_scan_job"

    async with session_scope() as session:
        updated = await get_monitor_by_target(session, target_id)
    assert updated is not None
    assert updated.next_run_at > now


async def test_check_due_monitors_job_disables_an_opted_out_targets_monitor(db_schema) -> None:
    account_id, target_id = await _seed_target("opted-out@example.com")
    now = datetime.now(UTC)
    async with session_scope() as session:
        await create_monitor(
            session, target_id, account_id, cadence_hours=24, next_run_at=now - timedelta(minutes=1)
        )
        await set_opt_out(session, target_id, True)

    redis = _FakeRedis()
    await jobs.check_due_monitors_job({"redis": redis})

    assert redis.enqueued == []
    async with session_scope() as session:
        updated = await get_monitor_by_target(session, target_id)
    assert updated is not None
    assert updated.enabled is False


async def test_detect_regression_job_records_and_notifies_a_new_critical_alert(
    db_schema, monkeypatch
) -> None:
    account_id, target_id = await _seed_target("regression@example.com")
    await _seed_scan(target_id, [], 100.0, "regression@example.com")
    async with session_scope() as session:
        await create_monitor(
            session, target_id, account_id, cadence_hours=24, next_run_at=datetime.now(UTC)
        )
    # Score stays within 10 points of the first scan so only the
    # new_critical event fires here, not a simultaneous score_drop — that
    # combination is covered by packages/monitoring/tests/test_diff.py.
    second_scan = await _seed_scan(
        target_id, [_finding("fp-new")], 95.0, "regression@example.com"
    )

    delivered = {}

    async def fake_notify(event):
        delivered["event"] = event
        from vigilo_notification.models import DeliveryResult

        return DeliveryResult(delivered=True)

    monkeypatch.setattr(jobs, "notify", fake_notify)

    await jobs.detect_regression_job({}, str(second_scan.job_id))

    assert delivered["event"].occurrences[0].event_type == "new_critical"

    async with session_scope() as session:
        result = await session.execute(select(AlertRow).where(AlertRow.target_id == target_id))
        alerts = result.scalars().all()
    assert len(alerts) == 1
    assert alerts[0].type == "new_critical"
    assert alerts[0].sent_at is not None


async def test_detect_regression_job_is_a_noop_without_a_monitor(db_schema, monkeypatch) -> None:
    _account_id, target_id = await _seed_target("no-monitor@example.com")
    scan = await _seed_scan(target_id, [], 100.0, "no-monitor@example.com")

    called = False

    async def fake_notify(event):
        nonlocal called
        called = True
        from vigilo_notification.models import DeliveryResult

        return DeliveryResult(delivered=True)

    monkeypatch.setattr(jobs, "notify", fake_notify)

    await jobs.detect_regression_job({}, str(scan.job_id))

    assert called is False


async def test_record_scan_failed_alert_job_records_and_notifies(db_schema, monkeypatch) -> None:
    account_id, target_id = await _seed_target("failed-scan@example.com")
    now = datetime.now(UTC)
    async with session_scope() as session:
        await create_monitor(session, target_id, account_id, cadence_hours=24, next_run_at=now)
        job = await create_scan_job(
            session, target_id, Tier.PASSIVE, "failed-scan@example.com", "0.1"
        )
        job = await advance(session, job.id, "authorized")
        job = await advance(session, job.id, "probing")
        job = await advance(session, job.id, "failed")

    async def fake_notify(event):
        from vigilo_notification.models import DeliveryResult

        return DeliveryResult(delivered=True)

    monkeypatch.setattr(jobs, "notify", fake_notify)

    await jobs.record_scan_failed_alert_job({}, str(job.id), "probing failed")

    async with session_scope() as session:
        result = await session.execute(select(AlertRow).where(AlertRow.target_id == target_id))
        alerts = result.scalars().all()
    assert len(alerts) == 1
    assert alerts[0].type == "scan_failed"
    assert alerts[0].scan_id is None
    assert alerts[0].sent_at is not None
