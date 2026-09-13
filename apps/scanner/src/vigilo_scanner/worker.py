"""`uv run arq vigilo_scanner.worker.WorkerSettings --app-dir apps/scanner/src`

Reads `REDIS_URL` via `vigilo_core.config` — the same env var `apps/api`
uses to enqueue jobs, so both ends of the queue point at the same Redis.
"""

from __future__ import annotations

from arq.connections import RedisSettings
from vigilo_core.config import config
from vigilo_core.errors import ErrorCode, StructuredError
from vigilo_orchestrator.jobs import run_scan_job, verify_ownership_job


def _redis_settings() -> RedisSettings:
    cfg = config()
    if not cfg.redis_url:
        raise StructuredError(ErrorCode.CONFIGURATION_ERROR, "REDIS_URL is not set")
    return RedisSettings.from_dsn(cfg.redis_url)


class WorkerSettings:
    functions = [run_scan_job, verify_ownership_job]
    redis_settings = _redis_settings()
