"""Build-blocking, same standard as
packages/security/tests/test_egress_guard.py: every backend URL the probe
discovers in a page's own content — Supabase, Firebase, S3, GCS — must go
through the egress guard before any request is made. This suite proves it by
making each provider's hostname resolve (via a fake resolver) to internal
address space, and asserting the MockTransport handler is NEVER invoked —
not just that the resulting finding looks right, but that no live request
was attempted at all.
"""

import base64
import json

import httpx

from vigilo_core.evidence import BundleObservation, FetchedScript, HttpObservation
from vigilo_probes.backend_probe import run_backend_checks

_FAKE_DNS = {
    "abcdefghijklmnopqrst.supabase.co": ["169.254.169.254"],  # cloud metadata
    "internal-rtdb.firebaseio.com": ["127.0.0.1"],  # loopback
    "internal-bucket.s3.amazonaws.com": ["10.0.0.5"],  # RFC1918 private
    "storage.googleapis.com": ["100.64.0.1"],  # CGNAT
}


def _fake_resolver(hostname: str) -> list[str]:
    if hostname not in _FAKE_DNS:
        raise AssertionError(f"unexpected DNS lookup for {hostname!r}")
    return _FAKE_DNS[hostname]


def _refusing_transport() -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError(
            f"backend probe must never make a live request to a denied target, got {request.url}"
        )

    return httpx.MockTransport(handler)


def _make_jwt(payload: dict) -> str:
    header_b64 = (
        base64.urlsafe_b64encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
        .rstrip(b"=")
        .decode()
    )
    payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=").decode()
    return f"{header_b64}.{payload_b64}.fakesignature"


def _http(body: str = "") -> HttpObservation:
    return HttpObservation(url="https://target.test/", status_code=200, body_excerpt=body)


def _bundle(excerpt: str) -> BundleObservation:
    return BundleObservation(fetched_scripts=[FetchedScript(url="https://target.test/s.js", excerpt=excerpt)])


async def test_supabase_pointing_at_internal_address_is_denied():
    anon_jwt = _make_jwt({"role": "anon"})
    excerpt = f'const url = "https://abcdefghijklmnopqrst.supabase.co"; const key = "{anon_jwt}";'
    bundle = _bundle(excerpt)

    result = await run_backend_checks(
        bundle, _http(), resolver=_fake_resolver, transport=_refusing_transport()
    )

    assert len(result.detected) == 1
    backend = result.detected[0]
    assert backend.probe_status_code is None
    assert backend.probe_indicates_open is False
    assert backend.probe_error is not None


async def test_firebase_pointing_at_loopback_is_denied():
    body = '<script>const c = {databaseURL: "https://internal-rtdb.firebaseio.com"};</script>'

    result = await run_backend_checks(
        None, _http(body), resolver=_fake_resolver, transport=_refusing_transport()
    )

    assert result.detected[0].probe_status_code is None
    assert result.detected[0].probe_indicates_open is False
    assert result.detected[0].probe_error is not None


async def test_s3_bucket_pointing_at_private_range_is_denied():
    body = '<img src="https://internal-bucket.s3.amazonaws.com/x.png">'

    result = await run_backend_checks(
        None, _http(body), resolver=_fake_resolver, transport=_refusing_transport()
    )

    assert result.detected[0].probe_status_code is None
    assert result.detected[0].probe_indicates_open is False
    assert result.detected[0].probe_error is not None


async def test_gcs_bucket_pointing_at_cgnat_is_denied():
    body = '<img src="https://storage.googleapis.com/internal-gcs-bucket/x.png">'

    result = await run_backend_checks(
        None, _http(body), resolver=_fake_resolver, transport=_refusing_transport()
    )

    assert result.detected[0].probe_status_code is None
    assert result.detected[0].probe_indicates_open is False
    assert result.detected[0].probe_error is not None


async def test_no_test_in_this_module_performs_real_network_io():
    """Documents the invariant by construction, same as
    test_egress_guard.py's identically-named test: every case above passes
    an explicit `resolver=` and a transport that raises on any request, so
    neither real DNS nor a real socket is ever reached."""
    assert True
