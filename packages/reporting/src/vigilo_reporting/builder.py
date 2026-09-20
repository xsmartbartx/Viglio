"""build_report(): pure assembly of a `ReportDocument` from already-fetched
data. Deliberate deviation from `docs/modules.md` §6's literal
`build_report(scan_id) -> Report` sketch (matching the precedent Phase 3 set
for `resolve_authorization`) — this module has no `persistence`/`checks`
dependency, so it cannot self-fetch a scan by id. The caller (an `apps/api`
handler) fetches `Scan`/`Finding` rows via `vigilo_orchestrator` and builds
`manifests_by_check_id` from `vigilo_checks.REGISTRY`.

Idempotent by construction: `generated_at` is a required parameter, not
`datetime.now()` — the same scan rendered twice (once for the web view,
later for a PDF) must produce byte-identical output, per this module's own
documented boundary. `remediations_by_check_id` (Phase 5) is just another
already-fetched input to that guarantee, not an exception to it — given the
same dict, output is identical. The caller may legitimately pass a
different cache snapshot across two renders of the same scan (template
placeholder before `generate_remediations_job` finishes, cached Claude text
after) — expected and self-healing, and it only ever changes remediation
prose, never score/grade/verdict, per docs/adr/ADR-0004-llm-boundary.md.
"""

from __future__ import annotations

from datetime import datetime

from vigilo_core.models import CheckManifest, Finding, Score
from vigilo_reporting.models import (
    EvidenceView,
    RemediationPrompt,
    RemediationView,
    ReportDocument,
    ReportFinding,
)
from vigilo_reporting.remediation import template_remediation

_VERDICT_ORDER = {"failed": 0, "passed": 1, "inconclusive": 2, "not_applicable": 3}
_SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4, "passed": 5}


def _sort_key(finding: Finding) -> tuple[int, int, str]:
    return (
        _VERDICT_ORDER.get(finding.verdict.value, 99),
        _SEVERITY_ORDER.get(finding.severity.value, 99),
        finding.check_id,
    )


def _to_report_finding(
    finding: Finding,
    manifest: CheckManifest,
    generated_at: datetime,
    remediations_by_check_id: dict[str, RemediationPrompt],
    suppressed_fingerprints: frozenset[str],
) -> ReportFinding:
    prompt = remediations_by_check_id.get(finding.check_id) or template_remediation(
        finding, manifest
    )
    remediation = RemediationView(**prompt.model_dump(exclude={"check_id"}))

    evidence = None
    if finding.evidence is not None:
        evidence = EvidenceView(
            matched_indicator=finding.evidence.matched_indicator,
            request_summary=finding.evidence.request_summary,
            redaction_applied=finding.evidence.redaction_applied,
            captured_at=finding.evidence.captured_at,
        )

    return ReportFinding(
        check_id=finding.check_id,
        category=manifest.category,
        title=finding.title,
        severity=finding.severity,
        confidence=finding.confidence,
        verdict=finding.verdict,
        summary=finding.summary,
        remediation=remediation,
        references=manifest.references,
        evidence=evidence,
        fingerprint=finding.fingerprint,
        suppressed=finding.fingerprint in suppressed_fingerprints,
    )


def build_report(
    target_origin: str,
    score: Score,
    findings: list[Finding],
    manifests_by_check_id: dict[str, CheckManifest],
    generated_at: datetime,
    remediations_by_check_id: dict[str, RemediationPrompt] | None = None,
    suppressed_fingerprints: frozenset[str] | None = None,
) -> ReportDocument:
    """`score` is never recomputed from `suppressed_fingerprints` — a
    suppression is presentation-only (marks a finding, never changes
    score/grade), so score history, monitoring's regression detection, and
    the public badge all keep reading the one true, unfiltered number
    (docs/build-roadmap.md's post-Phase-9 suppression entry has the full
    reasoning for why this is deliberate, not an oversight)."""
    remediations = remediations_by_check_id or {}
    suppressed = suppressed_fingerprints or frozenset()
    ordered = sorted(findings, key=_sort_key)
    report_findings = [
        _to_report_finding(
            finding, manifests_by_check_id[finding.check_id], generated_at, remediations, suppressed
        )
        for finding in ordered
    ]
    return ReportDocument(
        target_origin=target_origin,
        registry_version=score.registry_version,
        score=score,
        generated_at=generated_at,
        findings=report_findings,
    )
