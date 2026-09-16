from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr

from vigilo_core.models import Confidence, Severity, Tier, Verdict, VerificationMethod


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


class EntitlementsResponse(BaseModel):
    plan_id: str
    targets_limit: int | None
    scans_per_month_limit: int | None
    active_tier_allowed: bool
    share_links_allowed: bool
    monitoring_frequency: str | None
    api_keys_limit: int | None
    repo_connectors_limit: int | None

    model_config = {"from_attributes": True}


class AccountResponse(BaseModel):
    account_id: uuid.UUID
    email: str
    status: str
    created_at: datetime
    entitlements: EntitlementsResponse


class CheckoutRequest(BaseModel):
    plan_id: str


class CheckoutResponse(BaseModel):
    checkout_url: str


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


class EvidenceResponse(BaseModel):
    matched_indicator: str | None
    request_summary: str | None
    redaction_applied: bool | None
    captured_at: datetime


class RemediationResponse(BaseModel):
    source: Literal["template", "llm"]
    explanation: str
    impact: str
    remediation_steps: list[str]
    agent_prompt: str
    estimated_effort: Literal["trivial", "small", "medium", "large"] | None


class ReportFindingResponse(BaseModel):
    check_id: str
    category: str
    title: str
    severity: Severity
    confidence: Confidence
    verdict: Verdict
    summary: str
    remediation: RemediationResponse
    references: list[str]
    evidence: EvidenceResponse | None
    fingerprint: str


class ScanReportResponse(BaseModel):
    scan_job_id: uuid.UUID | None = None
    is_owner: bool | None = None
    target_origin: str
    registry_version: str
    score: float
    grade: str
    counts_by_severity: dict[Severity, int]
    generated_at: datetime
    findings: list[ReportFindingResponse]


class PdfStatusResponse(BaseModel):
    report_id: uuid.UUID
    status: str
    download_url: str | None = None


class ShareLinkCreate(BaseModel):
    expires_in_days: int | None = None


class ShareLinkCreateResponse(BaseModel):
    share_link_id: uuid.UUID
    token: str
    url: str
    expires_at: datetime | None


class ShareLinkResponse(BaseModel):
    share_link_id: uuid.UUID
    expires_at: datetime | None
    revoked_at: datetime | None
    view_count: int
    created_at: datetime


class ShareLinkRevokeResponse(BaseModel):
    share_link_id: uuid.UUID
    revoked_at: datetime
