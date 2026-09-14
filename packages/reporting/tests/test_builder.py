from __future__ import annotations

from datetime import UTC, datetime

from vigilo_core.models import (
    CheckManifest,
    Confidence,
    Evidence,
    Finding,
    Score,
    Severity,
    Tier,
    Verdict,
)
from vigilo_reporting.builder import build_report

_GENERATED_AT = datetime(2026, 9, 14, tzinfo=UTC)


def _manifest(check_id: str, category: str = "HDR") -> CheckManifest:
    return CheckManifest(
        check_id=check_id,
        category=category,
        title=f"title for {check_id}",
        description="desc",
        severity_default=Severity.HIGH,
        confidence=Confidence.CONFIRMED,
        weight=4,
        tier_required=Tier.PASSIVE,
        references=["https://example.com/ref"],
        remediation_template=f"fix {check_id}",
        introduced_in="0.1",
    )


def _finding(
    check_id: str, verdict: Verdict, severity: Severity = Severity.HIGH, with_evidence: bool = False
) -> Finding:
    evidence = None
    if with_evidence:
        evidence = Evidence(
            id="ev1",
            request_summary="GET https://example.com",
            response_summary="detail",
            matched_indicator="Set-Cookie: session=abc (no Secure)",
            redaction_applied=False,
            captured_at=_GENERATED_AT,
        )
    return Finding(
        check_id=check_id,
        verdict=verdict,
        severity=severity,
        confidence=Confidence.CONFIRMED,
        title=f"title for {check_id}",
        summary="summary",
        evidence=evidence,
        fingerprint=f"fp-{check_id}",
    )


def _score() -> Score:
    return Score(
        value=72.0, grade="C", registry_version="0.1", counts_by_severity={Severity.HIGH: 1}
    )


def test_build_report_assembles_the_document():
    findings = [_finding("VG-HDR-001", Verdict.FAILED)]
    manifests = {"VG-HDR-001": _manifest("VG-HDR-001")}

    report = build_report("https://example.com", _score(), findings, manifests, _GENERATED_AT)

    assert report.target_origin == "https://example.com"
    assert report.registry_version == "0.1"
    assert report.generated_at == _GENERATED_AT
    assert len(report.findings) == 1
    rf = report.findings[0]
    assert rf.category == "HDR"
    assert rf.remediation == "fix VG-HDR-001"
    assert rf.references == ["https://example.com/ref"]


def test_evidence_is_carried_through_when_present():
    findings = [_finding("VG-HDR-001", Verdict.FAILED, with_evidence=True)]
    manifests = {"VG-HDR-001": _manifest("VG-HDR-001")}

    report = build_report("https://example.com", _score(), findings, manifests, _GENERATED_AT)

    evidence = report.findings[0].evidence
    assert evidence is not None
    assert evidence.matched_indicator == "Set-Cookie: session=abc (no Secure)"


def test_evidence_is_none_when_the_finding_has_none():
    findings = [_finding("VG-HDR-001", Verdict.PASSED)]
    manifests = {"VG-HDR-001": _manifest("VG-HDR-001")}

    report = build_report("https://example.com", _score(), findings, manifests, _GENERATED_AT)

    assert report.findings[0].evidence is None


def test_findings_are_sorted_failed_by_severity_then_passed_then_inconclusive_then_not_applicable():
    findings = [
        _finding("VG-HDR-001", Verdict.NOT_APPLICABLE),
        _finding("VG-HDR-002", Verdict.INCONCLUSIVE),
        _finding("VG-HDR-003", Verdict.PASSED),
        _finding("VG-HDR-004", Verdict.FAILED, severity=Severity.LOW),
        _finding("VG-HDR-005", Verdict.FAILED, severity=Severity.CRITICAL),
    ]
    manifests = {f.check_id: _manifest(f.check_id) for f in findings}

    report = build_report("https://example.com", _score(), findings, manifests, _GENERATED_AT)

    assert [f.check_id for f in report.findings] == [
        "VG-HDR-005",
        "VG-HDR-004",
        "VG-HDR-003",
        "VG-HDR-002",
        "VG-HDR-001",
    ]


def test_build_report_is_idempotent_given_the_same_inputs():
    findings = [_finding("VG-HDR-001", Verdict.FAILED, with_evidence=True)]
    manifests = {"VG-HDR-001": _manifest("VG-HDR-001")}

    first = build_report("https://example.com", _score(), findings, manifests, _GENERATED_AT)
    second = build_report("https://example.com", _score(), findings, manifests, _GENERATED_AT)

    assert first == second
