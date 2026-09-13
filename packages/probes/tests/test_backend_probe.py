import base64
import json

import httpx

from vigilo_core.evidence import BundleObservation, FetchedScript, HttpObservation
from vigilo_probes.backend_probe import run_backend_checks

_FAKE_DNS = {
    "abcdefghijklmnopqrst.supabase.co": ["93.184.216.34"],
    "myapp-default-rtdb.firebaseio.com": ["93.184.216.34"],
    "my-bucket.s3.amazonaws.com": ["93.184.216.34"],
    "storage.googleapis.com": ["93.184.216.34"],
}


def _fake_resolver(hostname: str) -> list[str]:
    return _FAKE_DNS[hostname]


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


def _bundle(*excerpts: str) -> BundleObservation:
    return BundleObservation(
        fetched_scripts=[FetchedScript(url=f"https://target.test/s{i}.js", excerpt=e) for i, e in enumerate(excerpts)]
    )


async def test_no_backends_detected_returns_empty_observation():
    result = await run_backend_checks(None, _http("<html>nothing here</html>"), resolver=_fake_resolver)
    assert result.detected == []


async def test_supabase_anon_key_with_open_schema_is_flagged():
    anon_jwt = _make_jwt({"role": "anon", "iss": "supabase"})
    bundle = _bundle(f'const supabaseUrl = "https://abcdefghijklmnopqrst.supabase.co";\n'
                      f'const supabaseKey = "{anon_jwt}";')

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=json.dumps({"swagger": "2.0", "paths": {}, "definitions": {}}).encode())

    result = await run_backend_checks(
        bundle, _http(), resolver=_fake_resolver, transport=httpx.MockTransport(handler)
    )

    assert len(result.detected) == 1
    backend = result.detected[0]
    assert backend.provider == "supabase"
    assert backend.key_role == "anon"
    assert backend.probe_attempted is True
    assert backend.probe_indicates_open is True
    assert anon_jwt not in (backend.key_fingerprint or "")


async def test_supabase_anon_key_with_locked_down_schema_is_not_flagged():
    anon_jwt = _make_jwt({"role": "anon"})
    bundle = _bundle(f'"https://abcdefghijklmnopqrst.supabase.co" "{anon_jwt}"')

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, content=b'{"message":"No API key found"}')

    result = await run_backend_checks(
        bundle, _http(), resolver=_fake_resolver, transport=httpx.MockTransport(handler)
    )
    assert result.detected[0].probe_indicates_open is False


async def test_supabase_service_role_key_is_flagged_without_a_live_probe():
    """A service-role key leaking to the client is critical on its own —
    decoding the JWT's role claim is enough, no live request needed."""
    service_jwt = _make_jwt({"role": "service_role"})
    bundle = _bundle(f'"https://abcdefghijklmnopqrst.supabase.co" "{service_jwt}"')

    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("service_role detection must not make a live request")

    result = await run_backend_checks(
        bundle, _http(), resolver=_fake_resolver, transport=httpx.MockTransport(handler)
    )

    assert len(result.detected) == 1
    assert result.detected[0].key_role == "service_role"
    assert result.detected[0].probe_attempted is False


async def test_firebase_realtime_database_open_is_flagged():
    body = '<script>const firebaseConfig = {databaseURL: "https://myapp-default-rtdb.firebaseio.com"};</script>'

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b'{"users": {"1": "data"}}')

    result = await run_backend_checks(
        None, _http(body), resolver=_fake_resolver, transport=httpx.MockTransport(handler)
    )
    assert result.detected[0].provider == "firebase"
    assert result.detected[0].probe_indicates_open is True


async def test_firebase_realtime_database_closed_is_not_flagged():
    body = '<script>const firebaseConfig = {databaseURL: "https://myapp-default-rtdb.firebaseio.com"};</script>'

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"null")

    result = await run_backend_checks(
        None, _http(body), resolver=_fake_resolver, transport=httpx.MockTransport(handler)
    )
    assert result.detected[0].probe_indicates_open is False


async def test_s3_bucket_publicly_listable_is_flagged():
    body = '<img src="https://my-bucket.s3.amazonaws.com/photo.png">'

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"<ListBucketResult></ListBucketResult>")

    result = await run_backend_checks(
        None, _http(body), resolver=_fake_resolver, transport=httpx.MockTransport(handler)
    )
    assert result.detected[0].provider == "s3"
    assert result.detected[0].probe_indicates_open is True


async def test_s3_bucket_private_is_not_flagged():
    body = '<img src="https://my-bucket.s3.amazonaws.com/photo.png">'

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, content=b"<Error><Code>AccessDenied</Code></Error>")

    result = await run_backend_checks(
        None, _http(body), resolver=_fake_resolver, transport=httpx.MockTransport(handler)
    )
    assert result.detected[0].probe_indicates_open is False


async def test_gcs_bucket_publicly_listable_is_flagged():
    body = '<img src="https://storage.googleapis.com/my-gcs-bucket/photo.png">'

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b'{"items": []}')

    result = await run_backend_checks(
        None, _http(body), resolver=_fake_resolver, transport=httpx.MockTransport(handler)
    )
    assert result.detected[0].provider == "gcs"
    assert result.detected[0].probe_indicates_open is True
