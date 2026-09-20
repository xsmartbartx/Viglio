from __future__ import annotations

from vigilo_core.models import CheckManifest, Confidence, Finding, Severity, Tier, Verdict
from vigilo_reporting.sarif import build_sarif_report


def _manifest(
    check_id: str,
    severity: Severity = Severity.HIGH,
    cwe_id: str | None = "CWE-319",
) -> CheckManifest:
    return CheckManifest(
        check_id=check_id,
        category="HDR",
        title=f"title for {check_id}",
        description="desc",
        severity_default=severity,
        confidence=Confidence.CONFIRMED,
        weight=4,
        tier_required=Tier.PASSIVE,
        references=["https://example.com/ref"],
        remediation_template=f"fix {check_id}",
        introduced_in="0.1",
        cwe_id=cwe_id,
    )


def _finding(check_id: str, verdict: Verdict, severity: Severity = Severity.HIGH) -> Finding:
    return Finding(
        check_id=check_id,
        verdict=verdict,
        severity=severity,
        confidence=Confidence.CONFIRMED,
        title=f"title for {check_id}",
        summary=f"summary for {check_id}",
        fingerprint=f"fp-{check_id}",
    )


def test_build_sarif_report_has_the_required_top_level_shape():
    report = build_sarif_report("https://example.com", [], {})

    assert report["$schema"] == "https://json.schemastore.org/sarif-2.1.0.json"
    assert report["version"] == "2.1.0"
    assert len(report["runs"]) == 1
    assert report["runs"][0]["tool"]["driver"]["name"] == "Vigilo"


def test_passed_and_not_applicable_findings_are_excluded_from_results():
    findings = [
        _finding("VG-HDR-001", Verdict.PASSED),
        _finding("VG-HDR-002", Verdict.NOT_APPLICABLE),
        _finding("VG-HDR-003", Verdict.FAILED),
    ]
    manifests = {f.check_id: _manifest(f.check_id) for f in findings}

    report = build_sarif_report("https://example.com", findings, manifests)

    result_rule_ids = {r["ruleId"] for r in report["runs"][0]["results"]}
    assert result_rule_ids == {"VG-HDR-003"}


def test_inconclusive_findings_are_surfaced_as_a_note_not_hidden():
    findings = [_finding("VG-HDR-001", Verdict.INCONCLUSIVE, severity=Severity.CRITICAL)]
    manifests = {"VG-HDR-001": _manifest("VG-HDR-001", severity=Severity.CRITICAL)}

    report = build_sarif_report("https://example.com", findings, manifests)

    result = report["runs"][0]["results"][0]
    assert result["level"] == "note"
    assert "Could not be checked" in result["message"]["text"]


def test_failed_severity_maps_to_the_right_sarif_level():
    findings = [
        _finding("VG-AA-001", Verdict.FAILED, severity=Severity.CRITICAL),
        _finding("VG-AA-002", Verdict.FAILED, severity=Severity.MEDIUM),
        _finding("VG-AA-003", Verdict.FAILED, severity=Severity.LOW),
    ]
    manifests = {
        "VG-AA-001": _manifest("VG-AA-001", severity=Severity.CRITICAL),
        "VG-AA-002": _manifest("VG-AA-002", severity=Severity.MEDIUM),
        "VG-AA-003": _manifest("VG-AA-003", severity=Severity.LOW),
    }

    report = build_sarif_report("https://example.com", findings, manifests)
    levels = {r["ruleId"]: r["level"] for r in report["runs"][0]["results"]}

    assert levels == {"VG-AA-001": "error", "VG-AA-002": "warning", "VG-AA-003": "note"}


def test_rule_carries_cwe_tag_when_the_manifest_has_one():
    findings = [_finding("VG-HDR-001", Verdict.FAILED)]
    manifests = {"VG-HDR-001": _manifest("VG-HDR-001", cwe_id="CWE-319")}

    report = build_sarif_report("https://example.com", findings, manifests)

    rule = report["runs"][0]["tool"]["driver"]["rules"][0]
    assert "external/cwe/cwe-319" in rule["properties"]["tags"]


def test_rule_omits_cwe_tag_when_the_manifest_has_none():
    findings = [_finding("VG-LEG-001", Verdict.FAILED)]
    manifests = {"VG-LEG-001": _manifest("VG-LEG-001", cwe_id=None)}

    report = build_sarif_report("https://example.com", findings, manifests)

    rule = report["runs"][0]["tool"]["driver"]["rules"][0]
    assert not any(tag.startswith("external/cwe/") for tag in rule["properties"]["tags"])


def test_result_location_uses_the_target_origin_with_an_inert_region():
    findings = [_finding("VG-HDR-001", Verdict.FAILED)]
    manifests = {"VG-HDR-001": _manifest("VG-HDR-001")}

    report = build_sarif_report("https://example.com", findings, manifests)

    location = report["runs"][0]["results"][0]["locations"][0]["physicalLocation"]
    assert location["artifactLocation"]["uri"] == "https://example.com"
    assert location["region"] == {
        "startLine": 1,
        "startColumn": 1,
        "endLine": 1,
        "endColumn": 1,
    }


def test_result_fingerprint_matches_the_findings_own_fingerprint():
    findings = [_finding("VG-HDR-001", Verdict.FAILED)]
    manifests = {"VG-HDR-001": _manifest("VG-HDR-001")}

    report = build_sarif_report("https://example.com", findings, manifests)

    result = report["runs"][0]["results"][0]
    assert result["partialFingerprints"]["primaryLocationLineHash"] == "fp-VG-HDR-001"


def test_suppressed_findings_are_excluded_entirely():
    findings = [
        _finding("VG-HDR-001", Verdict.FAILED),
        _finding("VG-HDR-002", Verdict.FAILED),
    ]
    manifests = {
        "VG-HDR-001": _manifest("VG-HDR-001"),
        "VG-HDR-002": _manifest("VG-HDR-002"),
    }

    report = build_sarif_report(
        "https://example.com",
        findings,
        manifests,
        suppressed_fingerprints=frozenset({"fp-VG-HDR-001"}),
    )

    result_rule_ids = {r["ruleId"] for r in report["runs"][0]["results"]}
    assert result_rule_ids == {"VG-HDR-002"}
    rule_ids = {r["id"] for r in report["runs"][0]["tool"]["driver"]["rules"]}
    assert rule_ids == {"VG-HDR-002"}


def test_only_rules_for_reportable_findings_are_included():
    # Only FAILED/INCONCLUSIVE findings get a rule entry — a manifest
    # dict may contain far more checks than actually fired this scan.
    findings = [_finding("VG-HDR-001", Verdict.FAILED)]
    manifests = {
        "VG-HDR-001": _manifest("VG-HDR-001"),
        "VG-HDR-002": _manifest("VG-HDR-002"),
    }

    report = build_sarif_report("https://example.com", findings, manifests)

    rule_ids = {r["id"] for r in report["runs"][0]["tool"]["driver"]["rules"]}
    assert rule_ids == {"VG-HDR-001"}
