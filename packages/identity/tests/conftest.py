from __future__ import annotations

from collections.abc import AsyncIterator

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from vigilo_persistence import session_scope
from vigilo_persistence.testing import temporary_schema

import vigilo_identity.orm  # noqa: F401  — registers AccountRow on Base.metadata


@pytest_asyncio.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    async with temporary_schema():
        async with session_scope() as session:
            yield session
