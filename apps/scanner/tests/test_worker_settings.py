from __future__ import annotations

from vigilo_orchestrator.jobs import (
    generate_remediations_job,
    render_report_pdf_job,
    run_scan_job,
    verify_ownership_job,
)
from vigilo_scanner.worker import WorkerSettings


def test_worker_registers_all_four_job_functions():
    assert WorkerSettings.functions == [
        run_scan_job,
        verify_ownership_job,
        render_report_pdf_job,
        generate_remediations_job,
    ]


def test_worker_reads_redis_settings_from_config():
    assert WorkerSettings.redis_settings is not None
