"""Test-only helpers. Every persistence-backed package's test suite needs the
same thing: create every table currently registered on `Base.metadata`
(whichever `orm.py` modules that test file happens to import), run the test,
drop everything. Centralized here so `identity`/`project`/`security`/
`orchestrator` don't each reinvent it.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy import text

from vigilo_persistence.base import Base
from vigilo_persistence.engine import get_engine

_RESET_SCHEMA = ("DROP SCHEMA IF EXISTS public CASCADE", "CREATE SCHEMA public")
# asyncpg's prepared-statement protocol rejects multiple ;-separated
# statements in one execute() call, unlike psycopg2's default cursor —
# hence two statements, not one string.


@asynccontextmanager
async def temporary_schema() -> AsyncIterator[None]:
    """Nukes and recreates the entire `public` schema before creating the
    tables registered on `Base.metadata` — not `Base.metadata.drop_all()`,
    which only knows about (and can therefore only correctly order the
    drop of) whichever `orm.py` modules the *calling test file* happened to
    import. A database left with extra tables it doesn't know about — e.g.
    from a developer manually running `alembic upgrade head` against the
    same local Postgres, or a prior manual/live smoke test — makes
    `drop_all()` fail outright on an unresolvable FK dependency, or (worse,
    found the hard way during Phase 3's live end-to-end verification)
    silently leak leftover rows into a test that assumes an empty table.
    This is a test-only helper against a database dedicated to this
    project; a full schema reset is safe and simplest.
    """
    engine = get_engine()
    async with engine.begin() as conn:
        for statement in _RESET_SCHEMA:
            await conn.execute(text(statement))
        await conn.run_sync(Base.metadata.create_all)
    try:
        yield
    finally:
        async with engine.begin() as conn:
            for statement in _RESET_SCHEMA:
                await conn.execute(text(statement))
