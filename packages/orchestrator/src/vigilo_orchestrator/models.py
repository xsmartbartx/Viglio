from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel
from vigilo_core.models import Severity, Tier


class ScanJob(BaseModel):
    id: uuid.UUID
    target_id: uuid.UUID
    tier: Tier
    requested_by: str | None
    registry_version: str
    status: str
    budget: dict | None
    queued_at: datetime
    started_at: datetime | None
    finished_at: datetime | None

    model_config = {"from_attributes": True}


class Scan(BaseModel):
    id: uuid.UUID
    job_id: uuid.UUID
    target_id: uuid.UUID
    registry_version: str
    score: float
    grade: str
    counts_by_severity: dict[Severity, int]
    duration_ms: int
    tier: Tier
    bundle_id: str | None

    model_config = {"from_attributes": True}
