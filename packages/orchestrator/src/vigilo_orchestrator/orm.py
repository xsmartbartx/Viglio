"""ScanJobRow / ScanRow / FindingRow
(docs/prooflight-vision-and-architecture.md §6.1, docs/modules.md §8).

`ScanRow.bundle_id` is a deliberate addition beyond the domain-model table —
the object-storage pointer to the sealed `EvidenceBundle` (`docs/data-model.md`
documents the deviation). FKs reference `targets.id`/`scan_jobs.id`/
`scans.id` by table name only; this module never imports `vigilo_project.orm`.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from vigilo_persistence.base import Base


class ScanJobRow(Base):
    __tablename__ = "scan_jobs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    target_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("targets.id"), index=True)
    tier: Mapped[str] = mapped_column(String(16))
    requested_by: Mapped[str | None] = mapped_column(String(255), default=None)
    registry_version: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(16), default="queued")
    budget: Mapped[dict | None] = mapped_column(JSON, default=None)
    queued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


class ScanRow(Base):
    __tablename__ = "scans"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("scan_jobs.id"), unique=True)
    target_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("targets.id"), index=True)
    registry_version: Mapped[str] = mapped_column(String(16))
    score: Mapped[float] = mapped_column(Float)
    grade: Mapped[str] = mapped_column(String(4))
    counts_by_severity: Mapped[dict] = mapped_column(JSON, default=dict)
    duration_ms: Mapped[int] = mapped_column(Integer)
    tier: Mapped[str] = mapped_column(String(16))
    bundle_id: Mapped[str | None] = mapped_column(String(64), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class FindingRow(Base):
    __tablename__ = "findings"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    scan_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("scans.id"), index=True)
    check_id: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(16))
    severity: Mapped[str] = mapped_column(String(16))
    confidence: Mapped[str] = mapped_column(String(16))
    title: Mapped[str] = mapped_column(String(255))
    summary: Mapped[str] = mapped_column(Text)
    evidence_id: Mapped[str | None] = mapped_column(String(64), default=None)
    fingerprint: Mapped[str] = mapped_column(String(128))
