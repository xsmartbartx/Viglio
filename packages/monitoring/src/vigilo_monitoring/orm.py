"""MonitorRow / AlertRow (docs/data-model.md, Phase 8).

FKs reference `targets.id`/`accounts.id`/`scans.id` by table name only —
this package never imports `vigilo_project.orm`/`vigilo_identity.orm`/
`vigilo_orchestrator.orm`, matching the "cross-module FK by table name
only" convention `docs/data-model.md` already documents.

`MonitorRow.account_id` and `AlertRow.target_id` are both deliberate
denormalizations — `Target` has no direct `account_id` (only via
`project_id -> Project.account_id`), and an alert must stay queryable by
target even if its owning `Monitor` is later deleted. Same precedent as
`scans.target_id` existing alongside `scan_jobs.target_id`.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from vigilo_persistence.base import Base


class MonitorRow(Base):
    __tablename__ = "monitors"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    target_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("targets.id"), unique=True, index=True
    )
    account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("accounts.id"), index=True)
    cadence_hours: Mapped[int] = mapped_column(Integer)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    next_run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    quiet_start_utc: Mapped[int | None] = mapped_column(Integer, default=None)
    quiet_end_utc: Mapped[int | None] = mapped_column(Integer, default=None)
    pending_score_drop: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AlertRow(Base):
    __tablename__ = "alerts"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    monitor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("monitors.id"), index=True)
    target_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("targets.id"), index=True)
    scan_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("scans.id"), index=True, default=None
    )
    """`null` for `scan_failed` — the job never reached `record_scan_result()`,
    so no `Scan` row exists to reference."""
    type: Mapped[str] = mapped_column(String(32))
    severity: Mapped[str | None] = mapped_column(String(16), default=None)
    fingerprint: Mapped[str | None] = mapped_column(String(128), default=None)
    dedupe_key: Mapped[str] = mapped_column(String(200))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    channel: Mapped[str] = mapped_column(String(16), default="email")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
