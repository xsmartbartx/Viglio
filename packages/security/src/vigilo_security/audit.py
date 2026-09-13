"""audit(): the append-only decision writer (docs/modules.md §2, ADR-0003).

Takes an already-open `AsyncSession` rather than opening its own — the
caller controls the transaction boundary, so
"resolve_authorization → audit write → create ScanJob" commits as one unit,
matching ADR-0003's "written to the audit trail before the scan is queued,
not after" and `docs/architecture.md` §4's sequence diagram (the
authorization decision is recorded before the orchestrator enqueues).

This is a deliberate, documented expansion of `security`'s dependency
footprint from "core only" to "core + persistence" — flagged per the
roadmap's standing rule #2 since it's part of the authorization model.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from vigilo_security.orm import AuditEventRow


@dataclass(frozen=True)
class AuditEvent:
    actor: str
    action: str
    subject: str
    account_id: uuid.UUID | None = None
    metadata: dict = field(default_factory=dict)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))


async def audit(session: AsyncSession, event: AuditEvent) -> None:
    row = AuditEventRow(
        account_id=event.account_id,
        actor=event.actor,
        action=event.action,
        subject=event.subject,
        event_metadata=event.metadata,
    )
    session.add(row)
    await session.flush()
