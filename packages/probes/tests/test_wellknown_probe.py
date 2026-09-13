import httpx

from vigilo_probes.wellknown_probe import run_wellknown

_FAKE_DNS = {"safe.test": ["93.184.216.34"], "empty.test": ["93.184.216.34"]}


def _fake_resolver(hostname: str) -> list[str]:
    return _FAKE_DNS[hostname]


def _handler_all_present(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, content=b"present")


def _handler_none_present(request: httpx.Request) -> httpx.Response:
    return httpx.Response(404)


def _handler_mixed(request: httpx.Request) -> httpx.Response:
    if request.url.path == "/robots.txt":
        return httpx.Response(200, content=b"User-agent: *")
    return httpx.Response(404)


async def test_all_paths_present():
    result = await run_wellknown(
        "https://safe.test",
        resolver=_fake_resolver,
        transport=httpx.MockTransport(_handler_all_present),
    )
    assert result.security_txt_present is True
    assert result.robots_txt_present is True
    assert result.sitemap_present is True
    assert result.manifest_present is True


async def test_no_paths_present():
    result = await run_wellknown(
        "https://empty.test",
        resolver=_fake_resolver,
        transport=httpx.MockTransport(_handler_none_present),
    )
    assert result.security_txt_present is False
    assert result.robots_txt_present is False
    assert result.sitemap_present is False
    assert result.manifest_present is False


async def test_mixed_presence():
    result = await run_wellknown(
        "https://safe.test", resolver=_fake_resolver, transport=httpx.MockTransport(_handler_mixed)
    )
    assert result.robots_txt_present is True
    assert result.sitemap_present is False


async def test_connection_error_treated_as_absent():
    def _raising_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("simulated connection failure")

    result = await run_wellknown(
        "https://safe.test",
        resolver=_fake_resolver,
        transport=httpx.MockTransport(_raising_handler),
    )
    assert result.security_txt_present is False
    assert result.robots_txt_present is False
