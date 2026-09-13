"""Vigilo orchestrator: owns the lifecycle of a scan — plan, enqueue, track,
assemble, finalise (docs/modules.md §8).
"""

from __future__ import annotations

from vigilo_orchestrator.errors import InvalidScanTransition, ScanJobNotFound
from vigilo_orchestrator.jobs import run_scan_job, verify_ownership_job
from vigilo_orchestrator.models import Scan, ScanJob
from vigilo_orchestrator.service import (
    advance,
    create_scan_job,
    get_scan_by_job_id,
    get_scan_job,
    record_scan_result,
)

__all__ = [
    "ScanJob",
    "Scan",
    "ScanJobNotFound",
    "InvalidScanTransition",
    "create_scan_job",
    "get_scan_job",
    "advance",
    "record_scan_result",
    "get_scan_by_job_id",
    "run_scan_job",
    "verify_ownership_job",
]
