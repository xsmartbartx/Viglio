"""Async engine construction.

`.env.example`'s `DATABASE_URL` deliberately stays a plain `postgresql://` —
it's the one canonical URL every tool (psql, this package, a future sync
Alembic invocation) can parse without knowing which async driver is in use.
This module is the single place that rewrites it to the `asyncpg` DBAPI at
engine-construction time, so nothing else in the codebase needs to know that
detail.
"""

from __future__ import annotations

from functools import lru_cache

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from vigilo_core.config import config
from vigilo_core.errors import ErrorCode, StructuredError

_SYNC_SCHEME = "postgresql://"
_ASYNC_SCHEME = "postgresql+asyncpg://"


def _to_asyncpg_url(database_url: str) -> str:
    if database_url.startswith(_ASYNC_SCHEME):
        return database_url
    if database_url.startswith(_SYNC_SCHEME):
        return _ASYNC_SCHEME + database_url[len(_SYNC_SCHEME) :]
    raise StructuredError(
        ErrorCode.CONFIGURATION_ERROR,
        "DATABASE_URL must use the postgresql:// or postgresql+asyncpg:// scheme",
    )


@lru_cache(maxsize=1)
def get_engine() -> AsyncEngine:
    """Return the process-wide async engine, built once and cached.

    Call `get_engine.cache_clear()` in tests that need a fresh engine after
    changing `DATABASE_URL`.
    """
    cfg = config()
    if not cfg.database_url:
        raise StructuredError(
            ErrorCode.CONFIGURATION_ERROR, "DATABASE_URL is not set"
        )
    return create_async_engine(_to_asyncpg_url(cfg.database_url), pool_pre_ping=True)
