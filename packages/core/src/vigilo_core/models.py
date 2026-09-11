"""Domain models shared across modules (docs/modules.md §1).

Phase 0 scope: enough to support the egress guard and to give the check
registry and probe/scoring work in later phases a stable starting point.
Persistence-backed entities (Account, Project, OwnershipProof, ScanJob,
MonitorSchedule, Alert, Report, ShareLink, ApiKey, Subscription, AuditEvent)
are deferred to the phase that actually persists them — see
docs/build-roadmap.md. Defining them now, with no repository behind them,
would just be dead schema.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class Severity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"
    PASSED = "passed"


class Confidence(StrEnum):
    CONFIRMED = "confirmed"
    INDICATED = "indicated"


class Tier(StrEnum):
    PASSIVE = "passive"
    ACTIVE = "active"


class Verdict(StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    INCONCLUSIVE = "inconclusive"
    NOT_APPLICABLE = "not_applicable"


class Target(BaseModel):
    """A scan target, identified by its canonical origin — the output of
    `vigilo_core.validation.validate_target_url`."""

    origin: str
    verification_status: Tier = Tier.PASSIVE
    verified_at: datetime | None = None


class CheckManifest(BaseModel):
    """Descriptor for one check in the registry. Identity format is
    `VG-<CATEGORY>-<NNN>`, e.g. `VG-HDR-014` — Vigilo's naming, translated
    from the descriptor shape in
    docs/prooflight-vision-and-architecture.md §7.1 (which used a `PF-`
    prefix under the draft brand)."""

    check_id: str = Field(pattern=r"^VG-[A-Z]{2,4}-\d{3,4}$")
    category: str
    title: str
    description: str
    severity_default: Severity
    confidence: Confidence
    weight: float = Field(ge=0)
    tier_required: Tier
    references: list[str] = Field(default_factory=list)
    remediation_template: str
    false_positive_notes: str = ""
    introduced_in: str
    deprecated_in: str | None = None


class Evidence(BaseModel):
    """A sealed, redacted observation that a finding is based on. Secret
    values never appear here — only fingerprints produced by
    `vigilo_core.redact.redact`."""

    id: str
    request_summary: str
    response_summary: str
    matched_indicator: str
    redaction_applied: bool
    captured_at: datetime


class Finding(BaseModel):
    """One check's verdict against one target, at one point in time."""

    check_id: str
    verdict: Verdict
    severity: Severity
    confidence: Confidence
    title: str
    summary: str
    evidence: Evidence | None = None
    fingerprint: str


class Score(BaseModel):
    """A deterministic 0-100 score plus grade
    (docs/prooflight-vision-and-architecture.md §7.3). Computed by the
    scoring module, defined here only as the shared shape."""

    value: float = Field(ge=0, le=100)
    grade: str
    registry_version: str
    counts_by_severity: dict[Severity, int] = Field(default_factory=dict)
