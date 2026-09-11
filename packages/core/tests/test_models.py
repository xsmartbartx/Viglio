import pytest
from pydantic import ValidationError as PydanticValidationError

from vigilo_core.models import (
    CheckManifest,
    Confidence,
    Evidence,
    Finding,
    Score,
    Severity,
    Target,
    Tier,
    Verdict,
)


def test_target_defaults_to_passive_tier():
    target = Target(origin="https://example.com")
    assert target.verification_status == Tier.PASSIVE
    assert target.verified_at is None


def test_check_manifest_accepts_well_formed_id():
    manifest = CheckManifest(
        check_id="VG-HDR-014",
        category="HDR",
        title="HSTS enforced",
        description="Checks Strict-Transport-Security is present.",
        severity_default=Severity.HIGH,
        confidence=Confidence.CONFIRMED,
        weight=1.5,
        tier_required=Tier.PASSIVE,
        remediation_template="Add a Strict-Transport-Security header.",
        introduced_in="0.1",
    )
    assert manifest.check_id == "VG-HDR-014"


@pytest.mark.parametrize("bad_id", ["PF-HDR-014", "VG-HDR-14", "vg-hdr-014", "VG_HDR_014"])
def test_check_manifest_rejects_malformed_id(bad_id):
    with pytest.raises(PydanticValidationError):
        CheckManifest(
            check_id=bad_id,
            category="HDR",
            title="x",
            description="x",
            severity_default=Severity.LOW,
            confidence=Confidence.INDICATED,
            weight=1,
            tier_required=Tier.PASSIVE,
            remediation_template="x",
            introduced_in="0.1",
        )


def test_finding_and_evidence_round_trip():
    evidence = Evidence(
        id="ev_1",
        request_summary="GET /",
        response_summary="200 OK, no HSTS header",
        matched_indicator="missing-header:strict-transport-security",
        redaction_applied=True,
        captured_at="2026-01-01T00:00:00Z",
    )
    finding = Finding(
        check_id="VG-HDR-014",
        verdict=Verdict.FAILED,
        severity=Severity.HIGH,
        confidence=Confidence.CONFIRMED,
        title="Missing HSTS header",
        summary="The response did not include Strict-Transport-Security.",
        evidence=evidence,
        fingerprint="fp_abc123",
    )
    assert finding.evidence.matched_indicator.startswith("missing-header")


def test_score_bounds_are_enforced():
    Score(value=0, grade="F", registry_version="0.1")
    Score(value=100, grade="A", registry_version="0.1")
    with pytest.raises(PydanticValidationError):
        Score(value=101, grade="A", registry_version="0.1")
