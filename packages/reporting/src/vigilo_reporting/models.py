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


class RemediationPrompt(BaseModel):
    """The redaction-gated fix content attached to one finding —
    docs/adr/ADR-0004-llm-boundary.md's structured shape. `source="template"`
    is the deterministic, always-available fallback derived purely from the
    check manifest; `source="llm"` is Claude-authored and only ever produced
    by `generate_remediation()`, never by `build_report()` directly."""

    check_id: str
    source: Literal["template", "llm"] = "template"
    explanation: str
    impact: str
    remediation_steps: list[str]
    agent_prompt: str
    estimated_effort: Literal["trivial", "small", "medium", "large"] | None = None


class RemediationView(BaseModel):
    """`RemediationPrompt` minus `check_id` — the shape actually embedded in
    a `ReportFinding`, which already carries its own `check_id`."""

    source: Literal["template", "llm"]
    explanation: str
    impact: str
    remediation_steps: list[str]
    agent_prompt: str
    estimated_effort: Literal["trivial", "small", "medium", "large"] | None


class ReportFinding(BaseModel):
    check_id: str
    category: str
    title: str
    severity: Severity
    confidence: Confidence
    verdict: Verdict
    summary: str
    remediation: RemediationView
    references: list[str]
    evidence: EvidenceView | None
    fingerprint: str
    # True when the target owner has accepted this finding as a known risk
    # (post-Phase-9's suppression workflow, docs/build-roadmap.md). Never
    # changes score/grade — presentation only, per that entry's reasoning.
    suppressed: bool = False


class ReportDocument(BaseModel):
    target_origin: str
    registry_version: str
    score: Score
    generated_at: datetime
    findings: list[ReportFinding]
