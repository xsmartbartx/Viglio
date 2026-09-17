"""check_rate(): a Redis-backed, fixed-window rate limiter — closes
`docs/security.md`'s long-open "Rate governor (... Redis-backed)" table
entry, scoped here to the public API's per-API-key limits (Phase 9). The
separate, already-disclosed `resolve_authorization()` 24h scan-count
ceiling gap (still hardcoded `0` in `apps/api/src/vigilo_api/routers/
scans.py`) is a different concern and stays untouched.

Takes an injected Redis client rather than constructing its own — same
dependency-injection seam every other integration in this codebase uses
(`egress_guard.Resolver`, `ownership.TxtResolver`), so no test here ever
needs to fake Redis away; `apps/api`'s tests point it at the real local
instance `docker-compose.yml` already provides, matching how this
project tests Postgres-backed code against a real database rather than a
mock.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from redis.asyncio import Redis

from vigilo_core.config import config
from vigilo_core.errors import ErrorCode, StructuredError


@dataclass(frozen=True)
class RateLimitDecision:
    allowed: bool
    retry_after_seconds: int | None


@lru_cache(maxsize=1)
def get_redis_client() -> Redis:
    """Lazy singleton, same pattern as `apps/scanner`'s own
    `_redis_settings()` — one connection pool per process, built the first
    time it's actually needed."""
    cfg = config()
    if not cfg.redis_url:
        raise StructuredError(ErrorCode.CONFIGURATION_ERROR, "REDIS_URL is not set")
    return Redis.from_url(cfg.redis_url)


async def check_rate(
    redis: Redis, key: str, limit: int | None, window_seconds: int = 60
) -> RateLimitDecision:
    """`limit=None` always allows — mirrors `vigilo_billing.consume()`'s
    own "None means unlimited" convention, checked once here rather than
    scattered at every call site.

    Fixed window: `INCR` the key, set its TTL only on the first increment
    of a window (so a burst of requests doesn't keep extending it), and
    compare the count against `limit`. The increment always happens, even
    for the request that trips the limit — a strict fixed window, not a
    leaky bucket that would need to un-count a rejected request.
    """
    if limit is None:
        return RateLimitDecision(allowed=True, retry_after_seconds=None)

    count = await redis.incr(key)
    if count == 1:
        await redis.expire(key, window_seconds)

    if count <= limit:
        return RateLimitDecision(allowed=True, retry_after_seconds=None)

    ttl = await redis.ttl(key)
    return RateLimitDecision(allowed=False, retry_after_seconds=max(ttl, 1))
