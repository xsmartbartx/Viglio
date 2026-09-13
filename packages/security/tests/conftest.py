from __future__ import annotations

from collections.abc import AsyncIterator

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

import vigilo_identity.orm  # noqa: F401  — accounts table, referenced by audit_events' FK
import vigilo_security.orm  # noqa: F401  — registers AuditEventRow on Base.metadata
from vigilo_persistence import session_scope
from vigilo_persistence.testing import temporary_schema


@pytest_asyncio.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    async with temporary_schema(), session_scope() as session:
        yield session
