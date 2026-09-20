"""ProjectRow / TargetRow / OwnershipProofRow
(docs/prooflight-vision-and-architecture.md §6.1).

Foreign keys reference `accounts.id`/`projects.id`/`targets.id` by table
name only — this package never imports `vigilo_identity.orm` — so a single
shared Postgres holds the FK constraint without creating a Python-level
import cycle. See docs/modules.md §2a/§2b for why.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from vigilo_persistence.base import Base


class ProjectRow(Base):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("accounts.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TargetRow(Base):
    __tablename__ = "targets"
    __table_args__ = (UniqueConstraint("project_id", "origin"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    origin: Mapped[str] = mapped_column(String(255))
    verification_status: Mapped[str] = mapped_column(String(16), default="passive")
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    verification_method: Mapped[str | None] = mapped_column(String(32), default=None)
    opt_out_flag: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class OwnershipProofRow(Base):
    __tablename__ = "ownership_proofs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    target_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("targets.id"), index=True)
    method: Mapped[str] = mapped_column(String(32))
    nonce: Mapped[str] = mapped_column(String(64))
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


class SuppressionRow(Base):
    """A target owner's "known, accept it" decision on one finding
    (docs/prooflight-vision-and-architecture.md §6.2's never-built
    `acknowledged`/`muted` states, closed as a target-scoped suppression
    list rather than a full lifecycle retrofit — docs/build-roadmap.md's
    post-Phase-9 entry has the full reasoning). Keyed by `(target_id,
    fingerprint)`, the identical identity concept `detect_regression()`
    already tracks across scans — never `findings.id`, since every scan
    creates a fresh set of `FindingRow`s and a suppression must survive
    across all of them, matching `RemediationCacheRow`'s exact
    fingerprint-keyed-independent-of-any-one-scan precedent."""

    __tablename__ = "suppressions"
    __table_args__ = (UniqueConstraint("target_id", "fingerprint"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    target_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("targets.id"), index=True)
    fingerprint: Mapped[str] = mapped_column(String(128))
    # Informational/display only, like remediation_cache.check_id — the
    # fingerprint alone is what identifies the suppressed finding.
    check_id: Mapped[str] = mapped_column(String(32))
    reason: Mapped[str] = mapped_column(Text)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    created_by_account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("accounts.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
