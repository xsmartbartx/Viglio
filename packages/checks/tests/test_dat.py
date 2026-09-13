from datetime import UTC, datetime

from vigilo_checks import dat
from vigilo_core.evidence import BackendObservation, DetectedBackend, EvidenceBundle
from vigilo_core.models import Verdict


def _bundle(backends: BackendObservation | None) -> EvidenceBundle:
    return EvidenceBundle(
        bundle_id="test", target_origin="https://example.com", captured_at=datetime.now(UTC), backends=backends
    )


def _v(check, backends):
    return check.evaluate(_bundle(backends)).verdict


def test_all_dat_checks_are_inconclusive_without_backends_evidence():
    for check in dat.CHECKS:
        assert _v(check, None) == Verdict.INCONCLUSIVE, check.manifest.check_id


def test_all_dat_checks_pass_when_nothing_detected():
    empty = BackendObservation(detected=[])
    for check in dat.CHECKS:
        assert _v(check, empty) == Verdict.PASSED, check.manifest.check_id


def test_no_service_role_key_exposed():
    clean = BackendObservation(
        detected=[DetectedBackend(provider="supabase", url="https://x.supabase.co", key_role="anon")]
    )
    leaking = BackendObservation(
        detected=[
            DetectedBackend(
                provider="supabase",
                url="https://x.supabase.co",
                key_role="service_role",
                key_fingerprint="jwt:eyJh…(len=210)",
            )
        ]
    )

    assert _v(dat.CHECK_NO_SERVICE_ROLE_KEY_EXPOSED, clean) == Verdict.PASSED
    assert _v(dat.CHECK_NO_SERVICE_ROLE_KEY_EXPOSED, leaking) == Verdict.FAILED


def test_supabase_schema_not_introspectable():
    locked_down = BackendObservation(
        detected=[
            DetectedBackend(
                provider="supabase", url="https://x.supabase.co", key_role="anon", probe_indicates_open=False
            )
        ]
    )
    open_schema = BackendObservation(
        detected=[
            DetectedBackend(
                provider="supabase", url="https://x.supabase.co", key_role="anon", probe_indicates_open=True
            )
        ]
    )
    # A service_role finding should not also trip this anon-specific check.
    service_role_only = BackendObservation(
        detected=[
            DetectedBackend(
                provider="supabase", url="https://x.supabase.co", key_role="service_role", probe_indicates_open=True
            )
        ]
    )

    assert _v(dat.CHECK_SUPABASE_SCHEMA_NOT_INTROSPECTABLE, locked_down) == Verdict.PASSED
    assert _v(dat.CHECK_SUPABASE_SCHEMA_NOT_INTROSPECTABLE, open_schema) == Verdict.FAILED
    assert _v(dat.CHECK_SUPABASE_SCHEMA_NOT_INTROSPECTABLE, service_role_only) == Verdict.PASSED


def test_firebase_not_publicly_readable():
    closed = BackendObservation(
        detected=[DetectedBackend(provider="firebase", url="https://x.firebaseio.com", probe_indicates_open=False)]
    )
    open_db = BackendObservation(
        detected=[DetectedBackend(provider="firebase", url="https://x.firebaseio.com", probe_indicates_open=True)]
    )

    assert _v(dat.CHECK_FIREBASE_NOT_PUBLICLY_READABLE, closed) == Verdict.PASSED
    assert _v(dat.CHECK_FIREBASE_NOT_PUBLICLY_READABLE, open_db) == Verdict.FAILED


def test_no_public_bucket_listing():
    private_bucket = BackendObservation(
        detected=[DetectedBackend(provider="s3", url="https://b.s3.amazonaws.com", probe_indicates_open=False)]
    )
    public_s3 = BackendObservation(
        detected=[DetectedBackend(provider="s3", url="https://b.s3.amazonaws.com", probe_indicates_open=True)]
    )
    public_gcs = BackendObservation(
        detected=[
            DetectedBackend(provider="gcs", url="https://storage.googleapis.com/b", probe_indicates_open=True)
        ]
    )

    assert _v(dat.CHECK_NO_PUBLIC_BUCKET_LISTING, private_bucket) == Verdict.PASSED
    assert _v(dat.CHECK_NO_PUBLIC_BUCKET_LISTING, public_s3) == Verdict.FAILED
    assert _v(dat.CHECK_NO_PUBLIC_BUCKET_LISTING, public_gcs) == Verdict.FAILED
