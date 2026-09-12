from datetime import UTC, datetime

from vigilo_checks import hdr
from vigilo_core.evidence import EvidenceBundle, HttpObservation
from vigilo_core.models import Verdict


def _bundle(http: HttpObservation | None) -> EvidenceBundle:
    return EvidenceBundle(
        bundle_id="test", target_origin="https://example.com", captured_at=datetime.now(UTC), http=http
    )


def _http(headers: dict[str, str] | None = None, content_type: str | None = None) -> HttpObservation:
    return HttpObservation(
        url="https://example.com/", status_code=200, headers=headers or {}, content_type=content_type
    )


def _v(check, http):
    return check.evaluate(_bundle(http)).verdict


def test_all_hdr_checks_are_inconclusive_without_http_evidence():
    for check in hdr.CHECKS:
        assert _v(check, None) == Verdict.INCONCLUSIVE, check.manifest.check_id


def test_hsts_present():
    assert _v(hdr.CHECK_HSTS_PRESENT, _http({"strict-transport-security": "max-age=1"})) == Verdict.PASSED
    assert _v(hdr.CHECK_HSTS_PRESENT, _http({})) == Verdict.FAILED


def test_hsts_max_age():
    long_enough = _http({"strict-transport-security": "max-age=31536000"})
    too_short = _http({"strict-transport-security": "max-age=3600"})
    missing_directive = _http({"strict-transport-security": "includeSubDomains"})
    no_header = _http({})

    assert _v(hdr.CHECK_HSTS_MAX_AGE, long_enough) == Verdict.PASSED
    assert _v(hdr.CHECK_HSTS_MAX_AGE, too_short) == Verdict.FAILED
    assert _v(hdr.CHECK_HSTS_MAX_AGE, missing_directive) == Verdict.FAILED
    assert _v(hdr.CHECK_HSTS_MAX_AGE, no_header) == Verdict.INCONCLUSIVE


def test_hsts_include_subdomains():
    with_it = _http({"strict-transport-security": "max-age=1; includeSubDomains"})
    without_it = _http({"strict-transport-security": "max-age=1"})
    no_header = _http({})

    assert _v(hdr.CHECK_HSTS_INCLUDE_SUBDOMAINS, with_it) == Verdict.PASSED
    assert _v(hdr.CHECK_HSTS_INCLUDE_SUBDOMAINS, without_it) == Verdict.FAILED
    assert _v(hdr.CHECK_HSTS_INCLUDE_SUBDOMAINS, no_header) == Verdict.INCONCLUSIVE


def test_csp_present():
    assert _v(hdr.CHECK_CSP_PRESENT, _http({"content-security-policy": "default-src 'self'"})) == Verdict.PASSED
    assert _v(hdr.CHECK_CSP_PRESENT, _http({})) == Verdict.FAILED


def test_csp_no_unsafe_inline():
    safe = _http({"content-security-policy": "script-src 'self'"})
    unsafe = _http({"content-security-policy": "script-src 'self' 'unsafe-inline'"})
    unsafe_via_default = _http({"content-security-policy": "default-src 'unsafe-inline'"})
    no_header = _http({})

    assert _v(hdr.CHECK_CSP_NO_UNSAFE_INLINE, safe) == Verdict.PASSED
    assert _v(hdr.CHECK_CSP_NO_UNSAFE_INLINE, unsafe) == Verdict.FAILED
    assert _v(hdr.CHECK_CSP_NO_UNSAFE_INLINE, unsafe_via_default) == Verdict.FAILED
    assert _v(hdr.CHECK_CSP_NO_UNSAFE_INLINE, no_header) == Verdict.INCONCLUSIVE


def test_x_content_type_options():
    assert _v(hdr.CHECK_X_CONTENT_TYPE_OPTIONS, _http({"x-content-type-options": "nosniff"})) == Verdict.PASSED
    assert _v(hdr.CHECK_X_CONTENT_TYPE_OPTIONS, _http({"x-content-type-options": "sniff-away"})) == Verdict.FAILED
    assert _v(hdr.CHECK_X_CONTENT_TYPE_OPTIONS, _http({})) == Verdict.FAILED


def test_clickjacking_protection():
    via_xfo = _http({"x-frame-options": "DENY"})
    via_csp = _http({"content-security-policy": "frame-ancestors 'none'"})
    neither = _http({})

    assert _v(hdr.CHECK_CLICKJACKING_PROTECTION, via_xfo) == Verdict.PASSED
    assert _v(hdr.CHECK_CLICKJACKING_PROTECTION, via_csp) == Verdict.PASSED
    assert _v(hdr.CHECK_CLICKJACKING_PROTECTION, neither) == Verdict.FAILED


def test_referrer_policy():
    good = _http({"referrer-policy": "strict-origin-when-cross-origin"})
    unsafe = _http({"referrer-policy": "unsafe-url"})
    missing = _http({})

    assert _v(hdr.CHECK_REFERRER_POLICY, good) == Verdict.PASSED
    assert _v(hdr.CHECK_REFERRER_POLICY, unsafe) == Verdict.FAILED
    assert _v(hdr.CHECK_REFERRER_POLICY, missing) == Verdict.FAILED


def test_permissions_policy():
    assert _v(hdr.CHECK_PERMISSIONS_POLICY, _http({"permissions-policy": "camera=()"})) == Verdict.PASSED
    assert _v(hdr.CHECK_PERMISSIONS_POLICY, _http({})) == Verdict.FAILED


def test_server_header_no_version():
    clean = _http({"server": "cloudflare"})
    versioned = _http({"server": "Apache/2.4.41 (Ubuntu)"})
    absent = _http({})

    assert _v(hdr.CHECK_SERVER_NO_VERSION, clean) == Verdict.PASSED
    assert _v(hdr.CHECK_SERVER_NO_VERSION, versioned) == Verdict.FAILED
    assert _v(hdr.CHECK_SERVER_NO_VERSION, absent) == Verdict.PASSED


def test_x_powered_by_absent():
    assert _v(hdr.CHECK_X_POWERED_BY_ABSENT, _http({})) == Verdict.PASSED
    assert _v(hdr.CHECK_X_POWERED_BY_ABSENT, _http({"x-powered-by": "PHP/8.1"})) == Verdict.FAILED


def test_content_type_present():
    assert _v(hdr.CHECK_CONTENT_TYPE_PRESENT, _http(content_type="text/html")) == Verdict.PASSED
    assert _v(hdr.CHECK_CONTENT_TYPE_PRESENT, _http(content_type=None)) == Verdict.FAILED
