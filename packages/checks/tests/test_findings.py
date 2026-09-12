from datetime import UTC, datetime

from vigilo_checks import REGISTRY, run_registry
from vigilo_checks.registry import CheckResult
from vigilo_core.evidence import EvidenceBundle, HttpObservation
from vigilo_core.models import Verdict


def _bundle(headers: dict[str, str] | None = None) -> EvidenceBundle:
    return EvidenceBundle(
        bundle_id="b1",
        target_origin="https://example.com",
        captured_at=datetime.now(UTC),
        http=HttpObservation(url="https://example.com/", status_code=200, headers=headers or {}),
    )


def test_run_registry_produces_one_finding_per_check():
    findings = run_registry(_bundle(), REGISTRY)
    hdr_tls_ids = {c.manifest.check_id for c in REGISTRY}
    assert {f.check_id for f in findings} == hdr_tls_ids


def test_finding_carries_manifest_severity_and_confidence():
    findings = run_registry(_bundle(), REGISTRY)
    hsts_finding = next(f for f in findings if f.check_id == "VG-HDR-001")
    manifest = next(c.manifest for c in REGISTRY if c.manifest.check_id == "VG-HDR-001")
    assert hsts_finding.severity == manifest.severity_default
    assert hsts_finding.confidence == manifest.confidence


def test_fingerprint_is_stable_for_same_check_and_target():
    findings_a = run_registry(_bundle(), REGISTRY)
    findings_b = run_registry(_bundle(), REGISTRY)
    fp_a = {f.check_id: f.fingerprint for f in findings_a}
    fp_b = {f.check_id: f.fingerprint for f in findings_b}
    assert fp_a == fp_b


def test_fingerprint_differs_across_targets():
    from vigilo_checks.findings import to_findings

    check = next(c for c in REGISTRY if c.manifest.check_id == "VG-HDR-011")
    bundle_a = _bundle()
    bundle_b = EvidenceBundle(
        bundle_id="b2",
        target_origin="https://other.example",
        captured_at=datetime.now(UTC),
        http=HttpObservation(url="https://other.example/", status_code=200),
    )
    result: CheckResult = check.evaluate(bundle_a)
    finding_a = to_findings(bundle_a, [(check, result)])[0]
    finding_b = to_findings(bundle_b, [(check, result)])[0]
    assert finding_a.fingerprint != finding_b.fingerprint


def test_finding_with_matched_indicator_carries_evidence():
    findings = run_registry(_bundle({"x-powered-by": "PHP/8.1"}), REGISTRY)
    finding = next(f for f in findings if f.check_id == "VG-HDR-011")
    assert finding.verdict == Verdict.FAILED
    assert finding.evidence is not None
    assert finding.evidence.matched_indicator == "PHP/8.1"


def test_finding_without_matched_indicator_has_no_evidence():
    findings = run_registry(_bundle(), REGISTRY)
    finding = next(f for f in findings if f.check_id == "VG-HDR-011")
    assert finding.verdict == Verdict.PASSED
    assert finding.evidence is None
