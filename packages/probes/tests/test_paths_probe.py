import httpx

from vigilo_probes.paths_probe import run_paths

_FAKE_DNS = {"safe.test": ["93.184.216.34"], "empty.test": ["93.184.216.34"]}


def _fake_resolver(hostname: str) -> list[str]:
    return _FAKE_DNS[hostname]


def _handler_none_present(request: httpx.Request) -> httpx.Response:
    return httpx.Response(404)


async def test_all_candidates_checked_when_none_present():
    result = await run_paths(
        "https://empty.test",
        resolver=_fake_resolver,
        transport=httpx.MockTransport(_handler_none_present),
    )
    assert len(result.checked) == 29  # 4+5+4+5+4+4+3 across the 7 groups
    assert result.detected == []


async def test_a_reachable_repo_metadata_path_is_detected():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/.git/config":
            return httpx.Response(200, content=b"[core]")
        return httpx.Response(404)

    result = await run_paths(
        "https://safe.test", resolver=_fake_resolver, transport=httpx.MockTransport(handler)
    )

    assert len(result.detected) == 1
    assert result.detected[0].path == "/.git/config"
    assert result.detected[0].kind == "repo_metadata"
    assert result.detected[0].status_code == 200


async def test_directory_listing_requires_an_autoindex_marker():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/uploads/":
            return httpx.Response(200, content=b"<html><title>Index of /uploads</title></html>")
        if request.url.path == "/assets/":
            return httpx.Response(200, content=b"<html>a normal 200 page</html>")
        return httpx.Response(404)

    result = await run_paths(
        "https://safe.test", resolver=_fake_resolver, transport=httpx.MockTransport(handler)
    )

    kinds_detected = {d.path: d.kind for d in result.detected}
    assert kinds_detected == {"/uploads/": "directory_listing"}


async def test_connection_error_treated_as_not_detected():
    def raising_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("simulated connection failure")

    result = await run_paths(
        "https://safe.test",
        resolver=_fake_resolver,
        transport=httpx.MockTransport(raising_handler),
    )

    assert result.detected == []
    assert len(result.checked) == 29
