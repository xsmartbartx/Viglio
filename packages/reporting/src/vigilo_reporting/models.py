"""Pydantic shapes `build_report()` produces. Distinct from
`vigilo_core.models.Finding`/`Evidence`: these are *display* shapes — a
`ReportFinding` already carries its resolved `category`/`remediation`/
`references` from the check manifest, so `apps/web` never needs its own
copy of the check registry to render a report.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from vigilo_core.models import Confidence, Score, Severity, Verdict


class EvidenceView(BaseModel):
    matched_indicator: str | None
    request_summary: str | None
    redaction_applied: bool | None
    captured_at: datetime


class ReportFinding(BaseModel):
    check_id: str
    category: str
    title: str
    severity: Severity
    confidence: Confidence
    verdict: Verdict
    summary: str
    remediation: str
    references: list[str]
    evidence: EvidenceView | None
    fingerprint: str


class ReportDocument(BaseModel):
    target_origin: str
    registry_version: str
    score: Score
    generated_at: datetime
    findings: list[ReportFinding]


class RemediationPrompt(BaseModel):
    check_id: str
    text: str
    source: Literal["template", "llm"] = "template"
