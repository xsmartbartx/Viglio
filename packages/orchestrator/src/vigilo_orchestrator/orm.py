"""ScanJobRow / ScanRow / FindingRow / ReportRow / ShareLinkRow /
RemediationCacheRow (docs/prooflight-vision-and-architecture.md §6.1,
docs/modules.md §8).

`ScanRow.bundle_id` is a deliberate addition beyond the domain-model table —
the object-storage pointer to the sealed `EvidenceBundle` (`docs/data-model.md`
documents the deviation). FKs reference `targets.id`/`scan_jobs.id`/
`scans.id` by table name only; this module never imports `vigilo_project.orm`.

`FindingRow.matched_indicator`/`request_summary`/`redaction_applied` (Phase 4)
persist what `packages/checks`' `to_findings()` already computes per finding
but Phase 3 discarded — needed for evidence panels. No `captured_at` column:
every finding in one scan shares `ScanRow.created_at` as its capture moment
(`docs/data-model.md` documents the reuse).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
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
    matched_indicator: Mapped[str | None] = mapped_column(Text, default=None)
    request_summary: Mapped[str | None] = mapped_column(String(255), default=None)
    redaction_applied: Mapped[bool | None] = mapped_column(Boolean, default=None)


class ReportRow(Base):
    __tablename__ = "reports"
    __table_args__ = (UniqueConstraint("scan_id", "format"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    scan_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("scans.id"), index=True)
    format: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(16), default="pending")
    artefact_uri: Mapped[str | None] = mapped_column(String(255), default=None)
    branding_profile_id: Mapped[str | None] = mapped_column(String(64), default=None)
    generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ShareLinkRow(Base):
    __tablename__ = "share_links"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    report_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("reports.id"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    view_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RemediationCacheRow(Base):
    """Caches Claude-generated remediation by `(fingerprint, registry_version)`
    (docs/adr/ADR-0004-llm-boundary.md) — a repeat scan of the same target
    skips the LLM entirely on a cache hit. Only `source == "llm"` results are
    ever written here; template fallback text is free to recompute."""

    __tablename__ = "remediation_cache"
    __table_args__ = (UniqueConstraint("fingerprint", "registry_version"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    fingerprint: Mapped[str] = mapped_column(String(128))
    check_id: Mapped[str] = mapped_column(String(32), index=True)
    registry_version: Mapped[str] = mapped_column(String(16))
    explanation: Mapped[str] = mapped_column(Text)
    impact: Mapped[str] = mapped_column(Text)
    remediation_steps: Mapped[list] = mapped_column(JSON)
    agent_prompt: Mapped[str] = mapped_column(Text)
    estimated_effort: Mapped[str | None] = mapped_column(String(16), default=None)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
