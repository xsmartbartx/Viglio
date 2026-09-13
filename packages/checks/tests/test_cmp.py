from datetime import UTC, datetime

from vigilo_checks import cmp
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


def test_all_cmp_checks_are_inconclusive_without_http_evidence():
    for check in cmp.CHECKS:
        assert _v(check, None) == Verdict.INCONCLUSIVE, check.manifest.check_id


def test_tracker_without_consent_library():
    no_tracker = "<html>plain page</html>"
    tracker_with_cmp = '<script src="https://www.googletagmanager.com/gtag/js"></script><script src="https://consent.cookiebot.com/uc.js"></script>'
    tracker_without_cmp = '<script src="https://www.googletagmanager.com/gtag/js"></script>'

    assert _v(cmp.CHECK_TRACKER_WITHOUT_CONSENT_LIBRARY, _http(no_tracker)) == Verdict.NOT_APPLICABLE
    assert _v(cmp.CHECK_TRACKER_WITHOUT_CONSENT_LIBRARY, _http(tracker_with_cmp)) == Verdict.PASSED
    assert _v(cmp.CHECK_TRACKER_WITHOUT_CONSENT_LIBRARY, _http(tracker_without_cmp)) == Verdict.FAILED


def test_ga_uses_consent_mode():
    no_ga = "<html>plain page</html>"
    ga_with_consent = "gtag('consent', 'default', {'ad_storage': 'denied'}); gtag('config', 'G-XXX');"
    ga_without_consent = "gtag('config', 'G-XXX');"

    assert _v(cmp.CHECK_GA_USES_CONSENT_MODE, _http(no_ga)) == Verdict.NOT_APPLICABLE
    assert _v(cmp.CHECK_GA_USES_CONSENT_MODE, _http(ga_with_consent)) == Verdict.PASSED
    assert _v(cmp.CHECK_GA_USES_CONSENT_MODE, _http(ga_without_consent)) == Verdict.FAILED


def test_no_prechecked_marketing_checkbox():
    clean = '<input type="checkbox" name="terms">'
    prechecked_marketing = '<label>Subscribe to our newsletter</label><input type="checkbox" checked name="promo">'
    prechecked_unrelated = '<input type="checkbox" checked name="remember_me">'

    assert _v(cmp.CHECK_NO_PRECHECKED_MARKETING_CHECKBOX, _http(clean)) == Verdict.PASSED
    assert _v(cmp.CHECK_NO_PRECHECKED_MARKETING_CHECKBOX, _http(prechecked_marketing)) == Verdict.FAILED
    assert _v(cmp.CHECK_NO_PRECHECKED_MARKETING_CHECKBOX, _http(prechecked_unrelated)) == Verdict.PASSED


def test_consent_notice_references_privacy_policy():
    no_cookie_mention = "<html>plain page</html>"
    with_privacy_nearby = "We use cookies. See our Privacy Policy for details."
    without_privacy_nearby = "We use cookies to improve your experience. " + ("x" * 500) + " privacy"

    assert (
        _v(cmp.CHECK_CONSENT_NOTICE_REFERENCES_PRIVACY_POLICY, _http(no_cookie_mention))
        == Verdict.NOT_APPLICABLE
    )
    assert (
        _v(cmp.CHECK_CONSENT_NOTICE_REFERENCES_PRIVACY_POLICY, _http(with_privacy_nearby))
        == Verdict.PASSED
    )
    assert (
        _v(cmp.CHECK_CONSENT_NOTICE_REFERENCES_PRIVACY_POLICY, _http(without_privacy_nearby))
        == Verdict.FAILED
    )
