from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from vigilo_core.models import Score, Tier
from vigilo_identity.repository import get_or_create_account
from vigilo_monitoring.repository import (
    count_monitors_for_account,
    create_monitor,
    disable_monitor,
    due_monitors,
    get_monitor_by_target,
    list_alerts_for_target,
    mark_alert_sent,
    record_alert,
    reschedule_monitor,
)
from vigilo_orchestrator.service import create_scan_job, record_scan_result
from vigilo_project.repository import create_target, get_or_create_default_project


async def _seed_target(session: AsyncSession, email: str) -> tuple[uuid.UUID, uuid.UUID]:
    account = await get_or_create_account(session, email=email)
    project = await get_or_create_default_project(session, account.id)
    target = await create_target(session, project.id, "https://example.com")
    return account.id, target.id


async def _seed_scan(session: AsyncSession, target_id: uuid.UUID) -> uuid.UUID:
    job = await create_scan_job(session, target_id, Tier.PASSIVE, "owner@example.com", "0.1")
    score = Score(value=90.0, grade="A", registry_version="0.1")
    scan = await record_scan_result(session, job, [], score, duration_ms=10)
    return scan.id


async def test_create_monitor_is_idempotent_by_target(db_session: AsyncSession) -> None:
    account_id, target_id = await _seed_target(db_session, "monitor1@example.com")
    now = datetime.now(UTC)

    first = await create_monitor(db_session, target_id, account_id, 168, now + timedelta(hours=168))
    second = await create_monitor(
        db_session, target_id, account_id, 24, now + timedelta(hours=24)
    )

    assert second.id == first.id
    assert second.cadence_hours == 24


async def test_get_monitor_by_target_returns_none_when_none_exists(
    db_session: AsyncSession,
) -> None:
    _, target_id = await _seed_target(db_session, "monitor2@example.com")
    assert await get_monitor_by_target(db_session, target_id) is None


async def test_due_monitors_only_returns_enabled_monitors_past_next_run_at(
    db_session: AsyncSession,
) -> None:
    account_id, target_id = await _seed_target(db_session, "monitor3@example.com")
    now = datetime.now(UTC)

    due = await create_monitor(db_session, target_id, account_id, 24, now - timedelta(minutes=1))
    _, other_target_id = await _seed_target(db_session, "monitor4@example.com")
    await create_monitor(db_session, other_target_id, account_id, 24, now + timedelta(hours=1))

    results = await due_monitors(db_session, now)

    assert [m.id for m in results] == [due.id]


async def test_disabled_monitors_are_never_due(db_session: AsyncSession) -> None:
    account_id, target_id = await _seed_target(db_session, "monitor5@example.com")
    now = datetime.now(UTC)
    monitor = await create_monitor(
        db_session, target_id, account_id, 24, now - timedelta(minutes=1)
    )

    await disable_monitor(db_session, monitor.id)

    assert await due_monitors(db_session, now) == []


async def test_reschedule_monitor_updates_next_run_at_and_pending_score_drop(
    db_session: AsyncSession,
) -> None:
    account_id, target_id = await _seed_target(db_session, "monitor6@example.com")
    now = datetime.now(UTC)
    monitor = await create_monitor(db_session, target_id, account_id, 24, now)

    updated = await reschedule_monitor(
        db_session, monitor.id, now + timedelta(hours=48), pending_score_drop=True
    )

    assert updated is not None
    assert updated.pending_score_drop is True


async def test_count_monitors_for_account_only_counts_enabled(db_session: AsyncSession) -> None:
    account_id, target_id = await _seed_target(db_session, "monitor7@example.com")
    _, target_id_2 = await _seed_target(db_session, "monitor7b@example.com")
    now = datetime.now(UTC)

    monitor = await create_monitor(db_session, target_id, account_id, 24, now)
    await create_monitor(db_session, target_id_2, account_id, 24, now)
    await disable_monitor(db_session, monitor.id)

    assert await count_monitors_for_account(db_session, account_id) == 1


async def test_record_and_list_alerts_for_target(db_session: AsyncSession) -> None:
    account_id, target_id = await _seed_target(db_session, "monitor8@example.com")
    now = datetime.now(UTC)
    monitor = await create_monitor(db_session, target_id, account_id, 24, now)
    scan_id = await _seed_scan(db_session, target_id)

    alert = await record_alert(
        db_session,
        monitor_id=monitor.id,
        target_id=target_id,
        scan_id=scan_id,
        type="regressed",
        dedupe_key=f"{target_id}:fp1:regressed",
        severity="high",
        fingerprint="fp1",
    )

    assert alert.sent_at is None
    await mark_alert_sent(db_session, alert.id, now)

    alerts = await list_alerts_for_target(db_session, target_id)
    assert len(alerts) == 1
    assert alerts[0].sent_at is not None
