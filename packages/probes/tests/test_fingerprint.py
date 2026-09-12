from vigilo_core.evidence import HttpObservation
from vigilo_probes.fingerprint import fingerprint


def _http(headers: dict[str, str] | None = None, body: str = "") -> HttpObservation:
    return HttpObservation(
        url="https://example.com/",
        status_code=200,
        headers=headers or {},
        body_excerpt=body,
        body_size=len(body),
    )


def test_fingerprint_of_none_is_empty():
    fp = fingerprint(None)
    assert fp.hosting_signals == []
    assert fp.framework_signals == []


def test_fingerprint_detects_cloudflare_from_server_header():
    fp = fingerprint(_http(headers={"server": "cloudflare"}))
    assert "cloudflare" in fp.hosting_signals


def test_fingerprint_detects_vercel_from_presence_header():
    fp = fingerprint(_http(headers={"x-vercel-id": "abc123"}))
    assert "vercel" in fp.hosting_signals


def test_fingerprint_detects_nextjs_from_body():
    fp = fingerprint(_http(body='<script id="__NEXT_DATA__">{}</script>'))
    assert "next.js" in fp.framework_signals


def test_fingerprint_is_pure_and_deterministic():
    http = _http(headers={"server": "cloudflare"}, body="/_next/static/x.js")
    assert fingerprint(http) == fingerprint(http)
