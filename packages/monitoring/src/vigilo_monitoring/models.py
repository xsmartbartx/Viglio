"""Pydantic shapes returned by the repository — never the ORM row itself,
matching every other module's convention (see e.g. `vigilo_identity.models`).
`RegressionEvent`/`RegressionReport` are `diff.py`'s pure output, never
persisted directly — the caller decides which events become `Alert` rows.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class Monitor(BaseModel):
    id: uuid.UUID
    target_id: uuid.UUID
    account_id: uuid.UUID
    cadence_hours: int
    enabled: bool
    next_run_at: datetime
    quiet_start_utc: int | None
    quiet_end_utc: int | None
    pending_score_drop: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class Alert(BaseModel):
    id: uuid.UUID
    monitor_id: uuid.UUID
    target_id: uuid.UUID
    scan_id: uuid.UUID
    type: str
    severity: str | None
    fingerprint: str | None
    dedupe_key: str
    sent_at: datetime | None
    channel: str
    created_at: datetime

    model_config = {"from_attributes": True}


class RegressionEvent(BaseModel):
    """One alertable transition `detect_regression()` found. `resolved`
    transitions are computed internally but never surface here — see
    `diff.py`'s module docstring."""

    event_type: str  # new_critical | new_high | regressed | cert_expiry
    fingerprint: str
    check_id: str
    severity: str


class RegressionReport(BaseModel):
    events: list[RegressionEvent]
    score_drop: bool
    pending_score_drop: bool
    baseline_reset: bool
