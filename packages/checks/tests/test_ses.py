from datetime import UTC, datetime

from vigilo_checks import ses
from vigilo_core.evidence import CookieObservation, EvidenceBundle, HttpObservation
from vigilo_core.models import Verdict


def _bundle(http: HttpObservation | None) -> EvidenceBundle:
    return EvidenceBundle(
        bundle_id="test", target_origin="https://example.com", captured_at=datetime.now(UTC), http=http
    )


def _http(cookies=None, body: str = "") -> HttpObservation:
    return HttpObservation(
        url="https://example.com/", status_code=200, cookies=cookies or [], body_excerpt=body
    )


def _v(check, http):
    return check.evaluate(_bundle(http)).verdict


def test_all_ses_checks_are_inconclusive_without_http_evidence():
    for check in ses.CHECKS:
        assert _v(check, None) == Verdict.INCONCLUSIVE, check.manifest.check_id


def test_cookies_secure():
    secure = [CookieObservation(name="s", secure=True, http_only=True)]
    insecure = [CookieObservation(name="s", secure=False, http_only=True)]

    assert _v(ses.CHECK_COOKIES_SECURE, _http(secure)) == Verdict.PASSED
    assert _v(ses.CHECK_COOKIES_SECURE, _http(insecure)) == Verdict.FAILED
    assert _v(ses.CHECK_COOKIES_SECURE, _http([])) == Verdict.PASSED


def test_cookies_http_only():
    good = [CookieObservation(name="s", secure=True, http_only=True)]
    bad = [CookieObservation(name="s", secure=True, http_only=False)]

    assert _v(ses.CHECK_COOKIES_HTTP_ONLY, _http(good)) == Verdict.PASSED
    assert _v(ses.CHECK_COOKIES_HTTP_ONLY, _http(bad)) == Verdict.FAILED


def test_cookies_samesite_set():
    good = [CookieObservation(name="s", secure=True, http_only=True, same_site="Lax")]
    bad = [CookieObservation(name="s", secure=True, http_only=True, same_site=None)]

    assert _v(ses.CHECK_COOKIES_SAMESITE_SET, _http(good)) == Verdict.PASSED
    assert _v(ses.CHECK_COOKIES_SAMESITE_SET, _http(bad)) == Verdict.FAILED


def test_cookies_samesite_none_requires_secure():
    ok = [CookieObservation(name="s", secure=True, http_only=True, same_site="None")]
    bad = [CookieObservation(name="s", secure=False, http_only=True, same_site="None")]
    unrelated = [CookieObservation(name="s", secure=False, http_only=True, same_site="Lax")]

    assert _v(ses.CHECK_COOKIES_SAMESITE_NONE_REQUIRES_SECURE, _http(ok)) == Verdict.PASSED
    assert _v(ses.CHECK_COOKIES_SAMESITE_NONE_REQUIRES_SECURE, _http(bad)) == Verdict.FAILED
    assert _v(ses.CHECK_COOKIES_SAMESITE_NONE_REQUIRES_SECURE, _http(unrelated)) == Verdict.PASSED


def test_no_session_id_in_url():
    clean = '<a href="/about">About</a>'
    leaking = '<a href="/page?PHPSESSID=abc123">link</a>'

    assert _v(ses.CHECK_NO_SESSION_ID_IN_URL, _http(body=clean)) == Verdict.PASSED
    assert _v(ses.CHECK_NO_SESSION_ID_IN_URL, _http(body=leaking)) == Verdict.FAILED


def test_cookie_lifetime_sane():
    short_lived = [CookieObservation(name="session_id", secure=True, http_only=True, max_age=3600)]
    long_lived = [
        CookieObservation(name="auth_session", secure=True, http_only=True, max_age=60 * 24 * 3600)
    ]
    unrelated_long_lived = [
        CookieObservation(name="theme_pref", secure=True, http_only=True, max_age=60 * 24 * 3600)
    ]

    assert _v(ses.CHECK_COOKIE_LIFETIME_SANE, _http(short_lived)) == Verdict.PASSED
    assert _v(ses.CHECK_COOKIE_LIFETIME_SANE, _http(long_lived)) == Verdict.FAILED
    assert _v(ses.CHECK_COOKIE_LIFETIME_SANE, _http(unrelated_long_lived)) == Verdict.PASSED
