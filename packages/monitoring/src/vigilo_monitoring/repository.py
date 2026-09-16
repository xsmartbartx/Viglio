"""Monitor/Alert repository. Every function takes an already-open
`AsyncSession` — see `vigilo_identity.repository`'s module docstring for
why. Lookups return `None` rather than raising; callers (an `apps/api`
router or an ARQ job body) decide what a missing row means in their own
context, matching `vigilo_project.repository.get_target`'s precedent.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from vigilo_monitoring.models import Alert, Monitor
from vigilo_monitoring.orm import AlertRow, MonitorRow


async def create_monitor(
    session: AsyncSession,
    target_id: uuid.UUID,
    account_id: uuid.UUID,
    cadence_hours: int,
    next_run_at: datetime,
    quiet_start_utc: int | None = None,
    quiet_end_utc: int | None = None,
) -> Monitor:
    """Idempotent by `target_id` (unique constraint) — re-enabling a
    disabled monitor, or changing its cadence, updates the existing row
    rather than creating a duplicate. Matches `create_target`'s
    idempotent-by-origin precedent."""
    result = await session.execute(select(MonitorRow).where(MonitorRow.target_id == target_id))
    row = result.scalar_one_or_none()

    if row is None:
        row = MonitorRow(
            target_id=target_id,
            account_id=account_id,
            cadence_hours=cadence_hours,
            next_run_at=next_run_at,
            quiet_start_utc=quiet_start_utc,
            quiet_end_utc=quiet_end_utc,
        )
        session.add(row)
    else:
        row.cadence_hours = cadence_hours
        row.quiet_start_utc = quiet_start_utc
        row.quiet_end_utc = quiet_end_utc
        row.enabled = True

    await session.flush()
    return Monitor.model_validate(row)


async def get_monitor_by_target(session: AsyncSession, target_id: uuid.UUID) -> Monitor | None:
    result = await session.execute(select(MonitorRow).where(MonitorRow.target_id == target_id))
    row = result.scalar_one_or_none()
    return Monitor.model_validate(row) if row else None


async def due_monitors(session: AsyncSession, now: datetime) -> list[Monitor]:
    result = await session.execute(
        select(MonitorRow).where(MonitorRow.enabled.is_(True), MonitorRow.next_run_at <= now)
    )
    return [Monitor.model_validate(row) for row in result.scalars().all()]


async def disable_monitor(session: AsyncSession, monitor_id: uuid.UUID) -> Monitor | None:
    row = await session.get(MonitorRow, monitor_id)
    if row is None:
        return None
    row.enabled = False
    await session.flush()
    return Monitor.model_validate(row)


async def reschedule_monitor(
    session: AsyncSession,
    monitor_id: uuid.UUID,
    next_run_at: datetime,
    pending_score_drop: bool,
) -> Monitor | None:
    row = await session.get(MonitorRow, monitor_id)
    if row is None:
        return None
    row.next_run_at = next_run_at
    row.pending_score_drop = pending_score_drop
    await session.flush()
    return Monitor.model_validate(row)


async def count_monitors_for_account(session: AsyncSession, account_id: uuid.UUID) -> int:
    result = await session.execute(
        select(MonitorRow).where(MonitorRow.account_id == account_id, MonitorRow.enabled.is_(True))
    )
    return len(result.scalars().all())


async def record_alert(
    session: AsyncSession,
    monitor_id: uuid.UUID,
    target_id: uuid.UUID,
    scan_id: uuid.UUID,
    type: str,
    dedupe_key: str,
    severity: str | None = None,
    fingerprint: str | None = None,
) -> Alert:
    row = AlertRow(
        monitor_id=monitor_id,
        target_id=target_id,
        scan_id=scan_id,
        type=type,
        severity=severity,
        fingerprint=fingerprint,
        dedupe_key=dedupe_key,
    )
    session.add(row)
    await session.flush()
    return Alert.model_validate(row)


async def mark_alert_sent(session: AsyncSession, alert_id: uuid.UUID, sent_at: datetime) -> None:
    row = await session.get(AlertRow, alert_id)
    if row is not None:
        row.sent_at = sent_at
        await session.flush()


async def list_alerts_for_target(
    session: AsyncSession, target_id: uuid.UUID, limit: int = 20
) -> list[Alert]:
    result = await session.execute(
        select(AlertRow)
        .where(AlertRow.target_id == target_id)
        .order_by(AlertRow.created_at.desc())
        .limit(limit)
    )
    return [Alert.model_validate(row) for row in result.scalars().all()]
