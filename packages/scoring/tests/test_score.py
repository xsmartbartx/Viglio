from vigilo_core.models import CheckManifest, Confidence, Finding, Severity, Tier, Verdict
from vigilo_scoring import score


def _manifest(check_id: str, weight: float, tier: Tier = Tier.PASSIVE) -> CheckManifest:
    return CheckManifest(
        check_id=check_id,
        category="HDR",
        title="t",
        description="d",
        severity_default=Severity.HIGH,
        confidence=Confidence.CONFIRMED,
        weight=weight,
        tier_required=tier,
        remediation_template="r",
        introduced_in="0.1",
    )


def _finding(
    check_id: str, verdict: Verdict, severity: Severity, confidence: Confidence
) -> Finding:
    return Finding(
        check_id=check_id,
        verdict=verdict,
        severity=severity,
        confidence=confidence,
        title="t",
        summary="s",
        fingerprint="fp",
    )


def test_no_findings_scores_100_grade_a():
    result = score([], {}, "0.1")
    assert result.value == 100.0
    assert result.grade == "A"
    assert result.counts_by_severity == {}


def test_a_single_confirmed_critical_failure_deducts_full_weight():
    manifests = {"VG-X-001": _manifest("VG-X-001", weight=10)}
    findings = [_finding("VG-X-001", Verdict.FAILED, Severity.CRITICAL, Confidence.CONFIRMED)]

    result = score(findings, manifests, "0.1")

    assert result.value == 90.0  # 100 - (10 * 1.0 * 1.0)
    assert result.grade == "A"
    assert result.counts_by_severity == {Severity.CRITICAL: 1}


def test_indicated_confidence_halves_the_deduction():
    manifests = {"VG-X-001": _manifest("VG-X-001", weight=10)}
    findings = [_finding("VG-X-001", Verdict.FAILED, Severity.CRITICAL, Confidence.INDICATED)]

    result = score(findings, manifests, "0.1")

    assert result.value == 95.0  # 100 - (10 * 1.0 * 0.5)


def test_passed_and_inconclusive_findings_never_affect_the_score():
    manifests = {"VG-X-001": _manifest("VG-X-001", weight=10)}
    findings = [
        _finding("VG-X-001", Verdict.PASSED, Severity.CRITICAL, Confidence.CONFIRMED),
    ]
    assert score(findings, manifests, "0.1").value == 100.0

    findings = [
        _finding("VG-X-001", Verdict.INCONCLUSIVE, Severity.CRITICAL, Confidence.CONFIRMED),
    ]
    assert score(findings, manifests, "0.1").value == 100.0

    findings = [
        _finding("VG-X-001", Verdict.NOT_APPLICABLE, Severity.CRITICAL, Confidence.CONFIRMED),
    ]
    assert score(findings, manifests, "0.1").value == 100.0


def test_score_clamps_at_zero_when_deductions_exceed_100():
    manifests = {f"VG-X-{i:03d}": _manifest(f"VG-X-{i:03d}", weight=20) for i in range(10)}
    findings = [
        _finding(f"VG-X-{i:03d}", Verdict.FAILED, Severity.CRITICAL, Confidence.CONFIRMED)
        for i in range(10)
    ]

    result = score(findings, manifests, "0.1")
    assert result.value == 0.0
    assert result.grade == "F"


def test_grade_bands():
    def _score_for_deduction(deduction: float):
        m = {"VG-X-001": _manifest("VG-X-001", weight=deduction)}
        f = [_finding("VG-X-001", Verdict.FAILED, Severity.CRITICAL, Confidence.CONFIRMED)]
        return score(f, m, "0.1")

    assert _score_for_deduction(5).grade == "A"  # 95
    assert _score_for_deduction(15).grade == "B"  # 85
    assert _score_for_deduction(30).grade == "C"  # 70
    assert _score_for_deduction(50).grade == "D"  # 50
    assert _score_for_deduction(70).grade == "F"  # 30


def test_score_is_pure_and_deterministic():
    manifests = {"VG-X-001": _manifest("VG-X-001", weight=7)}
    findings = [_finding("VG-X-001", Verdict.FAILED, Severity.MEDIUM, Confidence.CONFIRMED)]

    result_a = score(findings, manifests, "0.1")
    result_b = score(findings, manifests, "0.1")
    assert result_a == result_b


def test_registry_version_is_recorded_on_the_score():
    result = score([], {}, "0.7")
    assert result.registry_version == "0.7"
