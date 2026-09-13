from datetime import UTC, datetime

from vigilo_core.evidence import (
    BackendObservation,
    BundleObservation,
    CookieObservation,
    DetectedBackend,
    EvidenceBundle,
    FetchedScript,
    FingerprintObservation,
    HttpObservation,
    TlsObservation,
    WellKnownObservation,
)


def _http() -> HttpObservation:
    return HttpObservation(
        url="https://example.com/",
        status_code=200,
        headers={"content-type": "text/html"},
        cookies=[CookieObservation(name="session", secure=True, http_only=True, same_site="Lax")],
        redirect_chain=[],
        body_excerpt="<html></html>",
        body_size=13,
        content_type="text/html",
        elapsed_ms=42.0,
    )


def test_cookie_observation_never_carries_a_value():
    cookie = CookieObservation(name="session", secure=True, http_only=True, same_site="Lax")
    assert not hasattr(cookie, "value")


def test_bundle_compute_id_is_stable_for_identical_content():
    http = _http()
    id_a = EvidenceBundle.compute_id("https://example.com", http, None, None)
    id_b = EvidenceBundle.compute_id("https://example.com", http, None, None)
    assert id_a == id_b


def test_bundle_compute_id_ignores_captured_at():
    """captured_at lives on the bundle itself, not inside compute_id's inputs,
    so two bundles built from identical observations at different times must
    still hash identically — that's what "content-addressed" means here."""
    http = _http()
    bundle_id = EvidenceBundle.compute_id("https://example.com", http, None, None)

    bundle_1 = EvidenceBundle(
        bundle_id=bundle_id,
        target_origin="https://example.com",
        captured_at=datetime(2026, 1, 1, tzinfo=UTC),
        http=http,
    )
    bundle_2 = EvidenceBundle(
        bundle_id=bundle_id,
        target_origin="https://example.com",
        captured_at=datetime(2026, 6, 1, tzinfo=UTC),
        http=http,
    )
    assert bundle_1.bundle_id == bundle_2.bundle_id


def test_bundle_compute_id_changes_when_content_changes():
    http_a = _http()
    http_b = _http().model_copy(update={"status_code": 404})

    id_a = EvidenceBundle.compute_id("https://example.com", http_a, None, None)
    id_b = EvidenceBundle.compute_id("https://example.com", http_b, None, None)
    assert id_a != id_b


def test_tls_observation_defaults_unverified_fields_to_none():
    tls = TlsObservation(attempted=True, verified=False, verify_error="hostname mismatch")
    assert tls.protocol_version is None
    assert tls.cert_subject is None
    assert tls.not_after is None


def test_fingerprint_observation_defaults_to_empty_lists():
    fp = FingerprintObservation()
    assert fp.hosting_signals == []
    assert fp.framework_signals == []


def test_cookie_observation_max_age_defaults_to_none():
    cookie = CookieObservation(name="session", secure=True, http_only=True)
    assert cookie.max_age is None
    cookie_with_age = CookieObservation(name="session", secure=True, http_only=True, max_age=3600)
    assert cookie_with_age.max_age == 3600


def test_fetched_script_defaults_to_no_error_and_empty_excerpt():
    script = FetchedScript(url="https://example.com/app.js", status_code=200, size=10, excerpt="x")
    assert script.fetch_error is None

    failed = FetchedScript(url="https://example.com/app.js", fetch_error="timed out")
    assert failed.status_code is None
    assert failed.size == 0


def test_bundle_observation_defaults_to_empty_list():
    assert BundleObservation().fetched_scripts == []


def test_wellknown_observation_defaults_to_all_absent():
    wk = WellKnownObservation()
    assert wk.security_txt_present is False
    assert wk.robots_txt_present is False
    assert wk.sitemap_present is False
    assert wk.manifest_present is False


def test_detected_backend_never_carries_the_raw_key():
    backend = DetectedBackend(
        provider="supabase",
        url="https://abc.supabase.co",
        key_role="anon",
        key_fingerprint="jwt:eyJh…(len=210,sha256=deadbeef)",
    )
    assert not hasattr(backend, "key")
    assert not hasattr(backend, "raw_key")
    assert "eyJh" in backend.key_fingerprint  # prefix only, not the full token


def test_backend_observation_defaults_to_empty_list():
    assert BackendObservation().detected == []


def test_bundle_compute_id_changes_when_bundle_field_changes():
    http = _http()
    id_without_bundle = EvidenceBundle.compute_id("https://example.com", http, None, None)
    id_with_bundle = EvidenceBundle.compute_id(
        "https://example.com",
        http,
        None,
        None,
        bundle=BundleObservation(
            fetched_scripts=[FetchedScript(url="https://example.com/a.js", status_code=200)]
        ),
    )
    assert id_without_bundle != id_with_bundle


def test_bundle_compute_id_changes_when_backends_field_changes():
    http = _http()
    id_a = EvidenceBundle.compute_id("https://example.com", http, None, None)
    id_b = EvidenceBundle.compute_id(
        "https://example.com",
        http,
        None,
        None,
        backends=BackendObservation(
            detected=[DetectedBackend(provider="supabase", url="https://abc.supabase.co")]
        ),
    )
    assert id_a != id_b
