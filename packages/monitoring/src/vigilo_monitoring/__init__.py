"""Vigilo monitoring: scheduling, scan diffing, alert persistence
(docs/modules.md §9). Depends on core, persistence, orchestrator, scoring.
"""

from __future__ import annotations

from vigilo_monitoring.diff import detect_regression
from vigilo_monitoring.models import Alert, Monitor, RegressionEvent, RegressionReport
from vigilo_monitoring.repository import (
    count_monitors_for_account,
    create_monitor,
    disable_monitor,
    due_monitors,
    get_monitor,
    get_monitor_by_target,
    list_alerts_for_target,
    mark_alert_sent,
    record_alert,
    reschedule_monitor,
)
from vigilo_monitoring.scheduling import compute_next_run_at

__all__ = [
    "Monitor",
    "Alert",
    "RegressionEvent",
    "RegressionReport",
    "detect_regression",
    "compute_next_run_at",
    "create_monitor",
    "get_monitor_by_target",
    "due_monitors",
    "get_monitor",
    "disable_monitor",
    "reschedule_monitor",
    "count_monitors_for_account",
    "record_alert",
    "mark_alert_sent",
    "list_alerts_for_target",
]
