"""Test-only helpers. Every persistence-backed package's test suite needs the
same thing: create every table currently registered on `Base.metadata`
(whichever `orm.py` modules that test file happens to import), run the test,
drop everything. Centralized here so `identity`/`project`/`security`/
`orchestrator` don't each reinvent it.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from vigilo_persistence.base import Base
from vigilo_persistence.engine import get_engine


@asynccontextmanager
async def temporary_schema() -> AsyncIterator[None]:
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    try:
        yield
    finally:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
