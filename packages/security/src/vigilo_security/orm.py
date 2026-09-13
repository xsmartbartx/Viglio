"""AuditEventRow — the append-only decision log ADR-0003 requires
("every authorization decision... written to an append-only audit trail
before the scan is queued"). Append-only is enforced at the database level
by a trigger, not here — see
`packages/persistence/migrations/versions/0002_audit_events_append_only.py`.

References `accounts.id` by table name only; this module never imports
`vigilo_identity.orm`, matching the FK-by-name convention documented in
`packages/project/src/vigilo_project/orm.py`.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from vigilo_persistence.base import Base


class AuditEventRow(Base):
    __tablename__ = "audit_events"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    account_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("accounts.id"), index=True, default=None
    )
    actor: Mapped[str] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(64))
    subject: Mapped[str] = mapped_column(String(255))
    event_metadata: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
