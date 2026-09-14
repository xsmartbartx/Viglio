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
    created_at: datetime

    model_config = {"from_attributes": True}


class Report(BaseModel):
    id: uuid.UUID
    scan_id: uuid.UUID
    format: str
    status: str
    artefact_uri: str | None
    branding_profile_id: str | None
    generated_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ShareLink(BaseModel):
    id: uuid.UUID
    report_id: uuid.UUID
    expires_at: datetime | None
    revoked_at: datetime | None
    view_count: int
    created_at: datetime

    model_config = {"from_attributes": True}
