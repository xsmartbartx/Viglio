"""Proves ADR-0003's append-only guarantee is real at the database level,
not just application-layer discipline — the property
`packages/persistence/migrations/versions/0002_audit_events_append_only.py`
adds via a `BEFORE UPDATE OR DELETE OR TRUNCATE` trigger. Runs the actual
migrations against the CI/local Postgres rather than `temporary_schema()`'s
`Base.metadata.create_all()` (which only knows ORM-declared columns/
constraints, not the raw-SQL trigger this test exists to verify).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import delete, select, text, update
from sqlalchemy.exc import DBAPIError

import vigilo_identity.orm  # noqa: F401
from vigilo_persistence import get_engine, session_scope
from vigilo_security.orm import AuditEventRow

_REPO_ROOT = Path(__file__).resolve().parents[3]
_ALEMBIC_INI = _REPO_ROOT / "packages" / "persistence" / "alembic.ini"


def _run_alembic(*args: str) -> None:
    subprocess.run(
        [sys.executable, "-m", "alembic", "-c", str(_ALEMBIC_INI), *args],
        check=True,
        cwd=_REPO_ROOT,
        capture_output=True,
    )


@pytest.fixture
async def migrated_schema():
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.execute(text("DROP FUNCTION IF EXISTS audit_events_no_update_delete() CASCADE"))
        await conn.execute(text("DROP TABLE IF EXISTS alembic_version"))
        tables = [
            "findings",
            "scans",
            "scan_jobs",
            "ownership_proofs",
            "targets",
            "projects",
            "audit_events",
            "accounts",
        ]
        for table in tables:
            await conn.execute(text(f"DROP TABLE IF EXISTS {table} CASCADE"))

    _run_alembic("upgrade", "head")
    try:
        yield
    finally:
        _run_alembic("downgrade", "base")
        async with engine.begin() as conn:
            await conn.execute(text("DROP TABLE IF EXISTS alembic_version"))


async def test_migrations_produce_all_eight_tables(migrated_schema):
    async with session_scope() as session:
        result = await session.execute(
            text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
        )
        tables = {row[0] for row in result}

    assert tables == {
        "accounts",
        "projects",
        "targets",
        "ownership_proofs",
        "scan_jobs",
        "scans",
        "findings",
        "audit_events",
        "alembic_version",
    }


async def test_update_on_audit_events_is_rejected(migrated_schema):
    async with session_scope() as session:
        row = AuditEventRow(actor="test", action="scan_authorized", subject="https://example.com")
        session.add(row)
        await session.flush()
        row_id = row.id

    async with session_scope() as session:
        stmt = update(AuditEventRow).where(AuditEventRow.id == row_id).values(action="tampered")
        with pytest.raises(DBAPIError, match="append-only"):
            await session.execute(stmt)
        # Postgres aborts the transaction on error; roll back before this
        # `async with` block's clean exit would otherwise try to commit it.
        await session.rollback()


async def test_delete_on_audit_events_is_rejected(migrated_schema):
    async with session_scope() as session:
        row = AuditEventRow(actor="test", action="scan_authorized", subject="https://example.com")
        session.add(row)
        await session.flush()
        row_id = row.id

    async with session_scope() as session:
        with pytest.raises(DBAPIError, match="append-only"):
            await session.execute(delete(AuditEventRow).where(AuditEventRow.id == row_id))
        await session.rollback()

    async with session_scope() as session:
        result = await session.execute(select(AuditEventRow).where(AuditEventRow.id == row_id))
        assert result.scalar_one_or_none() is not None


async def test_truncate_on_audit_events_is_rejected(migrated_schema):
    async with session_scope() as session:
        session.add(
            AuditEventRow(actor="test", action="scan_authorized", subject="https://example.com")
        )
        await session.flush()

    async with session_scope() as session:
        with pytest.raises(DBAPIError, match="append-only"):
            await session.execute(text("TRUNCATE audit_events"))
        await session.rollback()
