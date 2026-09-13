from __future__ import annotations

from collections.abc import AsyncIterator

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from vigilo_persistence import session_scope
from vigilo_persistence.testing import temporary_schema

import vigilo_identity.orm  # noqa: F401
import vigilo_orchestrator.orm  # noqa: F401
import vigilo_project.orm  # noqa: F401
import vigilo_security.orm  # noqa: F401


@pytest_asyncio.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    async with temporary_schema(), session_scope() as session:
        yield session


@pytest_asyncio.fixture
async def db_schema() -> AsyncIterator[None]:
    """For tests that exercise `vigilo_orchestrator.jobs`, which opens its
    own sessions via `session_scope()` rather than taking one as a param."""
    async with temporary_schema():
        yield
