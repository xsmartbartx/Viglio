from __future__ import annotations

from vigilo_orchestrator.jobs import run_scan_job, verify_ownership_job

from vigilo_scanner.worker import WorkerSettings


def test_worker_registers_both_job_functions():
    assert WorkerSettings.functions == [run_scan_job, verify_ownership_job]


def test_worker_reads_redis_settings_from_config():
    assert WorkerSettings.redis_settings is not None
