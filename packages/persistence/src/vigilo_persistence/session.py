"""Session construction. `session_scope()` is the seam ARQ job bodies and API
request handlers both use so a decision (e.g. resolve_authorization → audit
write → create ScanJob) commits as one transaction, per ADR-0003's
"before the scan is queued, not after" requirement.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from functools import lru_cache

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from vigilo_persistence.engine import get_engine


@lru_cache(maxsize=1)
def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(get_engine(), expire_on_commit=False)


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    """Open a session, commit on clean exit, roll back on any exception."""
    session = get_sessionmaker()()
    try:
        yield session
        await session.commit()
    except BaseException:
        await session.rollback()
        raise
    finally:
        await session.close()
