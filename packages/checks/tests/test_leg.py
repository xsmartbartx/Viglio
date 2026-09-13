from datetime import UTC, datetime

from vigilo_checks import leg
from vigilo_core.evidence import EvidenceBundle, HttpObservation
from vigilo_core.models import Verdict


def _bundle(http: HttpObservation | None) -> EvidenceBundle:
    return EvidenceBundle(
        bundle_id="test", target_origin="https://example.com", captured_at=datetime.now(UTC), http=http
    )


def _http(body: str = "") -> HttpObservation:
    return HttpObservation(url="https://example.com/", status_code=200, body_excerpt=body)


def _v(check, http):
    return check.evaluate(_bundle(http)).verdict


def test_all_leg_checks_are_inconclusive_without_http_evidence():
    for check in leg.CHECKS:
        assert _v(check, None) == Verdict.INCONCLUSIVE, check.manifest.check_id


def test_privacy_policy_linked_via_href():
    body = '<a href="/privacy-policy">Legal</a>'
    assert _v(leg.CHECK_PRIVACY_POLICY_LINKED, _http(body)) == Verdict.PASSED


def test_privacy_policy_linked_via_text():
    body = '<a href="/legal-stuff">Privacy Policy</a>'
    assert _v(leg.CHECK_PRIVACY_POLICY_LINKED, _http(body)) == Verdict.PASSED


def test_privacy_policy_missing():
    body = '<a href="/about">About us</a>'
    assert _v(leg.CHECK_PRIVACY_POLICY_LINKED, _http(body)) == Verdict.FAILED


def test_terms_linked():
    assert _v(leg.CHECK_TERMS_LINKED, _http('<a href="/terms-of-service">Terms</a>')) == Verdict.PASSED
    assert _v(leg.CHECK_TERMS_LINKED, _http('<a href="/x">x</a>')) == Verdict.FAILED


def test_cookie_policy_linked():
    assert _v(leg.CHECK_COOKIE_POLICY_LINKED, _http('<a href="/cookies">Cookie Policy</a>')) == Verdict.PASSED
    assert _v(leg.CHECK_COOKIE_POLICY_LINKED, _http('<a href="/x">x</a>')) == Verdict.FAILED


def test_contact_info_via_mailto():
    assert _v(leg.CHECK_CONTACT_INFO_PRESENT, _http('<a href="mailto:hi@example.com">Email us</a>')) == Verdict.PASSED


def test_contact_info_via_link_text():
    assert _v(leg.CHECK_CONTACT_INFO_PRESENT, _http('<a href="/reach-us">Contact</a>')) == Verdict.PASSED


def test_contact_info_missing():
    assert _v(leg.CHECK_CONTACT_INFO_PRESENT, _http('<a href="/about">About</a>')) == Verdict.FAILED
