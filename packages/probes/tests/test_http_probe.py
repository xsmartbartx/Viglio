"""No real sockets anywhere in this file: DNS is a fake resolver (same
pattern as packages/security/tests/test_egress_guard.py) and the HTTP
transport is httpx.MockTransport, so every request is handled entirely
in-process.
"""

import httpx
import pytest
from vigilo_probes.http_probe import TooManyRedirects, run_http
from vigilo_security.exceptions import EgressDenied

_FAKE_DNS: dict[str, list[str]] = {
    "safe.test": ["93.184.216.34"],
    "redirect-once.test": ["93.184.216.34"],
    "redirect-target.test": ["93.184.216.34"],
    "redirect-loop.test": ["93.184.216.34"],
    "redirect-no-location.test": ["93.184.216.34"],
    "internal-redirect.test": ["93.184.216.34"],
    "internal.test": ["169.254.1.1"],
}


def _fake_resolver(hostname: str) -> list[str]:
    if hostname not in _FAKE_DNS:
        raise AssertionError(f"unexpected DNS lookup for {hostname!r}")
    return _FAKE_DNS[hostname]


def _handler(request: httpx.Request) -> httpx.Response:
    host = request.headers.get("host", "")

    if host == "safe.test":
        return httpx.Response(
            200,
            headers=[
                ("content-type", "text/html"),
                ("set-cookie", "session=abc123; Secure; HttpOnly; SameSite=Lax"),
                ("set-cookie", "tracking=xyz"),
            ],
            content=b"<html>hello</html>",
        )
    if host == "redirect-once.test":
        return httpx.Response(302, headers=[("location", "https://redirect-target.test/")])
    if host == "redirect-target.test":
        return httpx.Response(200, content=b"landed")
    if host == "redirect-loop.test":
        return httpx.Response(302, headers=[("location", "https://redirect-loop.test/")])
    if host == "redirect-no-location.test":
        return httpx.Response(302)
    if host == "internal-redirect.test":
        return httpx.Response(302, headers=[("location", "https://internal.test/")])

    raise AssertionError(f"unexpected request Host {host!r}")


def _client() -> httpx.AsyncBaseTransport:
    return httpx.MockTransport(_handler)


async def test_run_http_captures_status_headers_and_cookies():
    obs = await run_http("https://safe.test", resolver=_fake_resolver, transport=_client())

    assert obs.status_code == 200
    assert obs.headers["content-type"] == "text/html"
    assert obs.body_excerpt == "<html>hello</html>"
    assert obs.body_size == len(b"<html>hello</html>")
    assert obs.redirect_chain == []

    cookie_names = {c.name for c in obs.cookies}
    assert cookie_names == {"session", "tracking"}
    session = next(c for c in obs.cookies if c.name == "session")
    assert session.secure is True
    assert session.http_only is True
    assert session.same_site == "Lax"
    tracking = next(c for c in obs.cookies if c.name == "tracking")
    assert tracking.secure is False


async def test_run_http_follows_one_redirect_and_records_chain():
    obs = await run_http("https://redirect-once.test", resolver=_fake_resolver, transport=_client())

    assert obs.status_code == 200
    assert obs.body_excerpt == "landed"
    assert obs.redirect_chain == ["https://redirect-once.test"]
    assert obs.url == "https://redirect-target.test/"


async def test_run_http_raises_on_redirect_loop():
    with pytest.raises(TooManyRedirects):
        await run_http("https://redirect-loop.test", resolver=_fake_resolver, transport=_client())


async def test_run_http_handles_redirect_without_location_gracefully():
    obs = await run_http(
        "https://redirect-no-location.test", resolver=_fake_resolver, transport=_client()
    )
    assert obs.status_code == 302
    assert obs.redirect_chain == []


async def test_redirect_into_internal_space_is_denied():
    with pytest.raises(EgressDenied):
        await run_http("https://internal-redirect.test", resolver=_fake_resolver, transport=_client())
