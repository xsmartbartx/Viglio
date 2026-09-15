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
from vigilo_reporting.models import RemediationPrompt

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
    assert rf.remediation.source == "template"
    assert rf.remediation.remediation_steps == ["fix VG-HDR-001"]
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


def _llm_prompt(check_id: str) -> RemediationPrompt:
    return RemediationPrompt(
        check_id=check_id,
        source="llm",
        explanation="llm explanation",
        impact="llm impact",
        remediation_steps=["llm step"],
        agent_prompt="llm agent prompt",
        estimated_effort="small",
    )


def test_a_cached_remediation_is_used_verbatim_when_present():
    findings = [_finding("VG-HDR-001", Verdict.FAILED)]
    manifests = {"VG-HDR-001": _manifest("VG-HDR-001")}
    remediations = {"VG-HDR-001": _llm_prompt("VG-HDR-001")}

    report = build_report(
        "https://example.com", _score(), findings, manifests, _GENERATED_AT, remediations
    )

    remediation = report.findings[0].remediation
    assert remediation.source == "llm"
    assert remediation.remediation_steps == ["llm step"]
    assert remediation.estimated_effort == "small"


def test_a_missing_cache_entry_falls_back_to_the_template_not_a_fresh_llm_call():
    findings = [_finding("VG-HDR-001", Verdict.FAILED), _finding("VG-HDR-002", Verdict.FAILED)]
    manifests = {
        "VG-HDR-001": _manifest("VG-HDR-001"),
        "VG-HDR-002": _manifest("VG-HDR-002"),
    }
    remediations = {"VG-HDR-001": _llm_prompt("VG-HDR-001")}  # VG-HDR-002 has no entry

    report = build_report(
        "https://example.com", _score(), findings, manifests, _GENERATED_AT, remediations
    )

    by_check_id = {f.check_id: f for f in report.findings}
    assert by_check_id["VG-HDR-001"].remediation.source == "llm"
    assert by_check_id["VG-HDR-002"].remediation.source == "template"
    assert by_check_id["VG-HDR-002"].remediation.remediation_steps == ["fix VG-HDR-002"]


def test_two_renders_with_different_remediation_snapshots_differ_only_in_remediation():
    findings = [_finding("VG-HDR-001", Verdict.FAILED)]
    manifests = {"VG-HDR-001": _manifest("VG-HDR-001")}

    before = build_report("https://example.com", _score(), findings, manifests, _GENERATED_AT)
    after = build_report(
        "https://example.com",
        _score(),
        findings,
        manifests,
        _GENERATED_AT,
        {"VG-HDR-001": _llm_prompt("VG-HDR-001")},
    )

    assert before.findings[0].remediation.source == "template"
    assert after.findings[0].remediation.source == "llm"
    before_dump = before.findings[0].model_dump(exclude={"remediation"})
    after_dump = after.findings[0].model_dump(exclude={"remediation"})
    assert before_dump == after_dump
