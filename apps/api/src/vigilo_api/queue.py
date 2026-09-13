"""The ARQ client pool. `apps/api` enqueues jobs here; `apps/scanner`'s
worker dequeues and runs them — communication between the control plane and
the scan zone is queue-only (docs/architecture.md §3), never a direct call.
"""

from __future__ import annotations

from arq import create_pool
from arq.connections import ArqRedis, RedisSettings

from vigilo_core.config import config
from vigilo_core.errors import ErrorCode, StructuredError

_pool: ArqRedis | None = None


async def get_arq_pool() -> ArqRedis:
    global _pool
    if _pool is None:
        cfg = config()
        if not cfg.redis_url:
            raise StructuredError(ErrorCode.CONFIGURATION_ERROR, "REDIS_URL is not set")
        _pool = await create_pool(RedisSettings.from_dsn(cfg.redis_url))
    return _pool
