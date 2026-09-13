from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr
from vigilo_core.models import Severity, Tier, VerificationMethod


class ScanSubmission(BaseModel):
    target_url: str
    email: EmailStr
    requested_tier: Tier = Tier.PASSIVE


class ScanSubmissionResponse(BaseModel):
    scan_job_id: uuid.UUID
    status: str
    granted_tier: Tier


class ScanStatusResponse(BaseModel):
    scan_job_id: uuid.UUID
    status: str
    target_origin: str
    tier: Tier
    score: float | None = None
    grade: str | None = None
    counts_by_severity: dict[Severity, int] | None = None
    finished_at: datetime | None = None


class AccountResponse(BaseModel):
    account_id: uuid.UUID
    email: str
    status: str
    created_at: datetime


class TargetCreate(BaseModel):
    origin: str


class TargetResponse(BaseModel):
    target_id: uuid.UUID
    origin: str
    verification_status: Tier
    verified_at: datetime | None = None
    verification_method: str | None = None


class VerificationInitiate(BaseModel):
    method: VerificationMethod


class VerificationInitiateResponse(BaseModel):
    proof_id: uuid.UUID
    method: VerificationMethod
    nonce: str
    instructions: str


class VerificationCheckResponse(BaseModel):
    proof_id: uuid.UUID
    status: str
