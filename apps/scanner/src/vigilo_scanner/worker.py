"""`uv run arq vigilo_scanner.worker.WorkerSettings --app-dir apps/scanner/src`

Reads `REDIS_URL` via `vigilo_core.config` — the same env var `apps/api`
uses to enqueue jobs, so both ends of the queue point at the same Redis.
"""

from __future__ import annotations

from arq.connections import RedisSettings
from arq.cron import cron

from vigilo_core.config import config
from vigilo_core.errors import ErrorCode, StructuredError
from vigilo_orchestrator.jobs import (
    generate_remediations_job,
    render_report_pdf_job,
    run_scan_job,
    verify_ownership_job,
)
from vigilo_scanner.jobs import (
    check_due_monitors_job,
    detect_regression_job,
    record_scan_failed_alert_job,
)


def _redis_settings() -> RedisSettings:
    cfg = config()
    if not cfg.redis_url:
        raise StructuredError(ErrorCode.CONFIGURATION_ERROR, "REDIS_URL is not set")
    return RedisSettings.from_dsn(cfg.redis_url)


class WorkerSettings:
    functions = [
        run_scan_job,
        verify_ownership_job,
        render_report_pdf_job,
        generate_remediations_job,
        detect_regression_job,
        record_scan_failed_alert_job,
    ]
    # Every 15 minutes — check_due_monitors_job itself is cheap (one query
    # plus per-monitor authorization/enqueue); no separate scheduler
    # process needed (docs/build-roadmap.md's Phase 8 entry).
    cron_jobs = [cron(check_due_monitors_job, minute=set(range(0, 60, 15)))]
    redis_settings = _redis_settings()
