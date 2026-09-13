from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from vigilo_identity.repository import get_or_create_account
from vigilo_security.audit import AuditEvent, audit
from vigilo_security.orm import AuditEventRow


async def test_audit_persists_an_event_with_no_account(db_session: AsyncSession) -> None:
    await audit(
        db_session,
        AuditEvent(actor="system", action="scan_denied", subject="https://denylisted.test"),
    )

    rows = (await db_session.execute(select(AuditEventRow))).scalars().all()
    assert len(rows) == 1
    assert rows[0].account_id is None
    assert rows[0].action == "scan_denied"


async def test_audit_persists_an_event_tied_to_an_account(db_session: AsyncSession) -> None:
    account = await get_or_create_account(db_session, email="owner@example.com")

    await audit(
        db_session,
        AuditEvent(
            actor="api",
            action="ownership_verified",
            subject="https://example.com",
            account_id=account.id,
            metadata={"method": "dns_txt"},
        ),
    )

    rows = (await db_session.execute(select(AuditEventRow))).scalars().all()
    assert len(rows) == 1
    assert rows[0].account_id == account.id
    assert rows[0].event_metadata == {"method": "dns_txt"}
