import httpx

from vigilo_core.evidence import HttpObservation
from vigilo_probes.bundle_probe import run_bundle

_FAKE_DNS = {
    "safe.test": ["93.184.216.34"],
    "cdn.test": ["93.184.216.34"],
    "internal-cdn.test": ["169.254.1.1"],
}


def _fake_resolver(hostname: str) -> list[str]:
    return _FAKE_DNS[hostname]


def _http(body_excerpt: str, url: str = "https://safe.test/") -> HttpObservation:
    return HttpObservation(url=url, status_code=200, body_excerpt=body_excerpt)


async def test_run_bundle_with_no_scripts_returns_empty_observation():
    http = _http("<html><body>no scripts here</body></html>")
    result = await run_bundle(http, resolver=_fake_resolver)
    assert result.fetched_scripts == []


async def test_run_bundle_fetches_same_origin_script():
    http = _http('<script src="/app.js"></script>')

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"console.log('hi')")

    result = await run_bundle(http, resolver=_fake_resolver, transport=httpx.MockTransport(handler))

    assert len(result.fetched_scripts) == 1
    script = result.fetched_scripts[0]
    assert script.url == "https://safe.test/app.js"
    assert script.status_code == 200
    assert script.excerpt == "console.log('hi')"
    assert script.fetch_error is None


async def test_run_bundle_fetches_third_party_script_through_egress_guard():
    http = _http('<script src="https://cdn.test/lib.js"></script>')

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"/* lib */")

    result = await run_bundle(http, resolver=_fake_resolver, transport=httpx.MockTransport(handler))

    assert result.fetched_scripts[0].url == "https://cdn.test/lib.js"
    assert result.fetched_scripts[0].fetch_error is None


async def test_run_bundle_denies_script_pointing_at_internal_address():
    """A hostile or compromised page whose bundle references a script host
    that resolves to internal address space must be denied by the egress
    guard exactly like the root page — never fetched, never silently
    skipped without a reason."""
    http = _http('<script src="https://internal-cdn.test/evil.js"></script>')

    result = await run_bundle(http, resolver=_fake_resolver)

    assert len(result.fetched_scripts) == 1
    script = result.fetched_scripts[0]
    assert script.fetch_error is not None
    assert script.status_code is None
    assert script.size == 0


async def test_run_bundle_caps_at_five_scripts():
    tags = "".join(f'<script src="/s{i}.js"></script>' for i in range(10))
    http = _http(tags)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"x")

    result = await run_bundle(http, resolver=_fake_resolver, transport=httpx.MockTransport(handler))
    assert len(result.fetched_scripts) == 5


async def test_run_bundle_deduplicates_repeated_script_urls():
    http = _http('<script src="/app.js"></script><script src="/app.js"></script>')

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"x")

    result = await run_bundle(http, resolver=_fake_resolver, transport=httpx.MockTransport(handler))
    assert len(result.fetched_scripts) == 1


async def test_run_bundle_ignores_data_uri_scripts():
    http = _http('<script src="data:text/javascript;base64,Y29uc29sZS5sb2coMSk="></script>')
    result = await run_bundle(http, resolver=_fake_resolver)
    assert result.fetched_scripts == []


async def test_run_bundle_records_fetch_error_without_raising():
    http = _http('<script src="/app.js"></script>')

    def raising_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("simulated failure")

    result = await run_bundle(
        http, resolver=_fake_resolver, transport=httpx.MockTransport(raising_handler)
    )
    assert result.fetched_scripts[0].fetch_error is not None
