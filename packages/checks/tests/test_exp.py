from datetime import UTC, datetime

from vigilo_checks import exp
from vigilo_core.evidence import EvidenceBundle, HttpObservation, WellKnownObservation
from vigilo_core.models import Verdict


def _bundle(wellknown=None, http=None) -> EvidenceBundle:
    return EvidenceBundle(
        bundle_id="test",
        target_origin="https://example.com",
        captured_at=datetime.now(UTC),
        wellknown=wellknown,
        http=http,
    )


def test_wellknown_checks_are_inconclusive_without_wellknown_evidence():
    for check in (exp.CHECK_SECURITY_TXT_PRESENT, exp.CHECK_ROBOTS_TXT_PRESENT, exp.CHECK_SITEMAP_PRESENT, exp.CHECK_MANIFEST_PRESENT):
        result = check.evaluate(_bundle())
        assert result.verdict == Verdict.INCONCLUSIVE, check.manifest.check_id


def test_verbose_error_check_is_inconclusive_without_http_evidence():
    result = exp.CHECK_NO_VERBOSE_ERROR_PAGE.evaluate(_bundle())
    assert result.verdict == Verdict.INCONCLUSIVE


def test_security_txt_present():
    present = WellKnownObservation(security_txt_present=True)
    absent = WellKnownObservation(security_txt_present=False)

    assert exp.CHECK_SECURITY_TXT_PRESENT.evaluate(_bundle(present)).verdict == Verdict.PASSED
    assert exp.CHECK_SECURITY_TXT_PRESENT.evaluate(_bundle(absent)).verdict == Verdict.FAILED


def test_robots_txt_present_never_fails():
    """Purely informational (INFO severity) — absence is reported but never
    scored as a failure."""
    present = WellKnownObservation(robots_txt_present=True)
    absent = WellKnownObservation(robots_txt_present=False)

    assert exp.CHECK_ROBOTS_TXT_PRESENT.evaluate(_bundle(present)).verdict == Verdict.PASSED
    assert exp.CHECK_ROBOTS_TXT_PRESENT.evaluate(_bundle(absent)).verdict == Verdict.PASSED


def test_sitemap_present_never_fails():
    assert exp.CHECK_SITEMAP_PRESENT.evaluate(_bundle(WellKnownObservation(sitemap_present=True))).verdict == Verdict.PASSED
    assert exp.CHECK_SITEMAP_PRESENT.evaluate(_bundle(WellKnownObservation(sitemap_present=False))).verdict == Verdict.PASSED


def test_manifest_present_never_fails():
    assert exp.CHECK_MANIFEST_PRESENT.evaluate(_bundle(WellKnownObservation(manifest_present=True))).verdict == Verdict.PASSED
    assert exp.CHECK_MANIFEST_PRESENT.evaluate(_bundle(WellKnownObservation(manifest_present=False))).verdict == Verdict.PASSED


def test_no_verbose_error_page():
    clean = HttpObservation(url="https://example.com/", status_code=200, body_excerpt="<html>Hello</html>")
    django_leak = HttpObservation(
        url="https://example.com/",
        status_code=500,
        body_excerpt="django.core.exceptions.ImproperlyConfigured: ...",
    )
    python_leak = HttpObservation(
        url="https://example.com/",
        status_code=500,
        body_excerpt="Traceback (most recent call last):\n  File ...",
    )

    assert exp.CHECK_NO_VERBOSE_ERROR_PAGE.evaluate(_bundle(http=clean)).verdict == Verdict.PASSED
    assert exp.CHECK_NO_VERBOSE_ERROR_PAGE.evaluate(_bundle(http=django_leak)).verdict == Verdict.FAILED
    assert exp.CHECK_NO_VERBOSE_ERROR_PAGE.evaluate(_bundle(http=python_leak)).verdict == Verdict.FAILED
