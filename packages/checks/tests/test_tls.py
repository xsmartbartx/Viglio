from datetime import UTC, datetime, timedelta

from vigilo_checks import tls
from vigilo_core.evidence import EvidenceBundle, HttpObservation, TlsObservation
from vigilo_core.models import Verdict


def _bundle(
    http: HttpObservation | None = None, tls_obs: TlsObservation | None = None
) -> EvidenceBundle:
    return EvidenceBundle(
        bundle_id="test",
        target_origin="https://example.com",
        captured_at=datetime.now(UTC),
        http=http,
        tls=tls_obs,
    )


def _http(url: str = "https://example.com/", body_excerpt: str = "") -> HttpObservation:
    return HttpObservation(url=url, status_code=200, body_excerpt=body_excerpt)


def _tls(**overrides) -> TlsObservation:
    defaults = dict(attempted=True, verified=True, protocol_version="TLSv1.3", cipher_name="TLS_AES_256_GCM_SHA384")
    defaults.update(overrides)
    return TlsObservation(**defaults)


def _v(check, http=None, tls_obs=None):
    return check.evaluate(_bundle(http, tls_obs)).verdict


# --- VG-TLS-001 ---------------------------------------------------------------


def test_https_enforced():
    assert _v(tls.CHECK_HTTPS_ENFORCED, http=_http("https://example.com/")) == Verdict.PASSED
    assert _v(tls.CHECK_HTTPS_ENFORCED, http=_http("http://example.com/")) == Verdict.FAILED
    assert _v(tls.CHECK_HTTPS_ENFORCED, http=None) == Verdict.INCONCLUSIVE


# --- VG-TLS-002 ---------------------------------------------------------------


def test_handshake_verifies():
    assert _v(tls.CHECK_HANDSHAKE_VERIFIES, tls_obs=_tls(verified=True)) == Verdict.PASSED
    assert (
        _v(tls.CHECK_HANDSHAKE_VERIFIES, tls_obs=_tls(verified=False, verify_error="expired"))
        == Verdict.FAILED
    )
    assert _v(tls.CHECK_HANDSHAKE_VERIFIES, tls_obs=None) == Verdict.INCONCLUSIVE


# --- VG-TLS-003 ---------------------------------------------------------------


def test_cert_not_expired():
    future = datetime.now(UTC) + timedelta(days=30)
    past = datetime.now(UTC) - timedelta(days=1)

    assert _v(tls.CHECK_CERT_NOT_EXPIRED, tls_obs=_tls(not_after=future)) == Verdict.PASSED
    assert _v(tls.CHECK_CERT_NOT_EXPIRED, tls_obs=_tls(not_after=past)) == Verdict.FAILED
    assert _v(tls.CHECK_CERT_NOT_EXPIRED, tls_obs=_tls(not_after=None)) == Verdict.INCONCLUSIVE
    assert _v(tls.CHECK_CERT_NOT_EXPIRED, tls_obs=None) == Verdict.INCONCLUSIVE


# --- VG-TLS-004 ---------------------------------------------------------------


def test_cert_not_expiring_soon():
    assert _v(tls.CHECK_CERT_NOT_EXPIRING_SOON, tls_obs=_tls(days_until_expiry=90)) == Verdict.PASSED
    assert _v(tls.CHECK_CERT_NOT_EXPIRING_SOON, tls_obs=_tls(days_until_expiry=5)) == Verdict.FAILED
    assert _v(tls.CHECK_CERT_NOT_EXPIRING_SOON, tls_obs=_tls(days_until_expiry=None)) == Verdict.INCONCLUSIVE


# --- VG-TLS-005 ---------------------------------------------------------------


def test_protocol_version_modern():
    assert _v(tls.CHECK_PROTOCOL_VERSION_MODERN, tls_obs=_tls(protocol_version="TLSv1.3")) == Verdict.PASSED
    assert _v(tls.CHECK_PROTOCOL_VERSION_MODERN, tls_obs=_tls(protocol_version="TLSv1.1")) == Verdict.FAILED
    assert (
        _v(tls.CHECK_PROTOCOL_VERSION_MODERN, tls_obs=_tls(protocol_version=None)) == Verdict.INCONCLUSIVE
    )


# --- VG-TLS-006 ---------------------------------------------------------------


def test_no_mixed_content():
    clean = _http("https://example.com/", body_excerpt="<img src='https://example.com/a.png'>")
    mixed = _http("https://example.com/", body_excerpt="<img src='http://example.com/a.png'>")
    plaintext_page = _http("http://example.com/", body_excerpt="<img src='http://x.com/a.png'>")

    assert _v(tls.CHECK_NO_MIXED_CONTENT, http=clean) == Verdict.PASSED
    assert _v(tls.CHECK_NO_MIXED_CONTENT, http=mixed) == Verdict.FAILED
    assert _v(tls.CHECK_NO_MIXED_CONTENT, http=plaintext_page) == Verdict.NOT_APPLICABLE
    assert _v(tls.CHECK_NO_MIXED_CONTENT, http=None) == Verdict.INCONCLUSIVE


# --- VG-TLS-007 ---------------------------------------------------------------


def test_cert_validity_window():
    now = datetime.now(UTC)
    short = _tls(not_before=now - timedelta(days=90), not_after=now + timedelta(days=308))
    long = _tls(not_before=now - timedelta(days=10), not_after=now + timedelta(days=800))

    assert _v(tls.CHECK_CERT_VALIDITY_WINDOW, tls_obs=short) == Verdict.PASSED
    assert _v(tls.CHECK_CERT_VALIDITY_WINDOW, tls_obs=long) == Verdict.FAILED
    assert (
        _v(tls.CHECK_CERT_VALIDITY_WINDOW, tls_obs=_tls(not_before=None, not_after=None))
        == Verdict.INCONCLUSIVE
    )


# --- VG-TLS-008 ---------------------------------------------------------------


def test_no_weak_cipher():
    assert _v(tls.CHECK_NO_WEAK_CIPHER, tls_obs=_tls(cipher_name="TLS_AES_256_GCM_SHA384")) == Verdict.PASSED
    assert _v(tls.CHECK_NO_WEAK_CIPHER, tls_obs=_tls(cipher_name="ECDHE-RSA-RC4-SHA")) == Verdict.FAILED
    assert _v(tls.CHECK_NO_WEAK_CIPHER, tls_obs=_tls(cipher_name=None)) == Verdict.INCONCLUSIVE
