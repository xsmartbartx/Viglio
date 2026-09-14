from __future__ import annotations

from vigilo_core.models import CheckManifest, Confidence, Finding, Severity, Tier, Verdict

from vigilo_reporting.remediation import generate_remediation


def _manifest() -> CheckManifest:
    return CheckManifest(
        check_id="VG-HDR-001",
        category="HDR",
        title="HSTS enforced",
        description="desc",
        severity_default=Severity.HIGH,
        confidence=Confidence.CONFIRMED,
        weight=8,
        tier_required=Tier.PASSIVE,
        references=["https://example.com/ref"],
        remediation_template="Add a Strict-Transport-Security header.",
        introduced_in="0.1",
    )


def _finding() -> Finding:
    return Finding(
        check_id="VG-HDR-001",
        verdict=Verdict.FAILED,
        severity=Severity.HIGH,
        confidence=Confidence.CONFIRMED,
        title="HSTS enforced",
        summary="No HSTS header present.",
        fingerprint="fp1",
    )


def test_returns_the_manifests_static_template_verbatim():
    prompt = generate_remediation(_finding(), _manifest())

    assert prompt.check_id == "VG-HDR-001"
    assert prompt.text == "Add a Strict-Transport-Security header."
    assert prompt.source == "template"


def test_stack_profile_is_accepted_but_does_not_change_the_output():
    without = generate_remediation(_finding(), _manifest())
    with_profile = generate_remediation(_finding(), _manifest(), stack_profile="nextjs")

    assert without.text == with_profile.text
