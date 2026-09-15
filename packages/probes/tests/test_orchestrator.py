import httpx

from vigilo_core.models import Tier
from vigilo_probes.orchestrator import run_probes

_FAKE_DNS = {"safe.test": ["93.184.216.34"]}


def _fake_resolver(hostname: str) -> list[str]:
    return _FAKE_DNS[hostname]


def _handler(request: httpx.Request) -> httpx.Response:
    if request.url.host != "93.184.216.34":
        raise AssertionError(f"unexpected request to {request.url}")
    if str(request.url.path) == "/":
        return httpx.Response(200, headers=[("server", "cloudflare")], content=b"hello")
    return httpx.Response(404)  # every wellknown/bundle sub-path: absent


async def test_run_probes_skips_tls_for_http_scheme():
    bundle = await run_probes(
        "http://safe.test", resolver=_fake_resolver, transport=httpx.MockTransport(_handler)
    )

    assert bundle.tls is None
    assert bundle.http.status_code == 200
    assert bundle.fingerprint is not None
    assert "cloudflare" in bundle.fingerprint.hosting_signals
    assert bundle.target_origin == "http://safe.test"
    assert bundle.wellknown is not None
    assert bundle.wellknown.robots_txt_present is False
    assert bundle.bundle is not None
    assert bundle.backends is not None
    assert bundle.paths is None  # tier defaults to Tier.PASSIVE


async def test_run_probes_populates_wellknown_when_present():
    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url.path) == "/":
            return httpx.Response(200, content=b"<html></html>")
        if str(request.url.path) == "/robots.txt":
            return httpx.Response(200, content=b"User-agent: *")
        return httpx.Response(404)

    bundle = await run_probes(
        "http://safe.test", resolver=_fake_resolver, transport=httpx.MockTransport(handler)
    )

    assert bundle.wellknown.robots_txt_present is True
    assert bundle.wellknown.sitemap_present is False


async def test_run_probes_fetches_linked_scripts_into_bundle():
    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url.path) == "/":
            return httpx.Response(200, content=b'<script src="/app.js"></script>')
        if str(request.url.path) == "/app.js":
            return httpx.Response(200, content=b"console.log(1)")
        return httpx.Response(404)

    bundle = await run_probes(
        "http://safe.test", resolver=_fake_resolver, transport=httpx.MockTransport(handler)
    )

    assert len(bundle.bundle.fetched_scripts) == 1
    assert bundle.bundle.fetched_scripts[0].excerpt == "console.log(1)"


async def test_run_probes_never_requests_paths_candidates_at_passive_tier():
    """The probe-layer half of the tier-gating guarantee
    (docs/adr/ADR-0003-scan-authorization-model.md): an unverified
    (passive-tier) target must never receive the `paths` probe's
    hidden-path-enumeration requests at all — not merely have the
    resulting findings filtered out afterward."""

    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url.path) == "/.git/HEAD":
            raise AssertionError("paths probe must never fire at passive tier")
        if str(request.url.path) == "/":
            return httpx.Response(200, content=b"hello")
        return httpx.Response(404)

    bundle = await run_probes(
        "http://safe.test",
        tier=Tier.PASSIVE,
        resolver=_fake_resolver,
        transport=httpx.MockTransport(handler),
    )

    assert bundle.paths is None


async def test_run_probes_runs_the_paths_probe_at_active_tier():
    """The positive counterpart to the test above — proves the gate isn't
    just permanently closed."""

    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url.path) == "/.git/config":
            return httpx.Response(200, content=b"[core]")
        if str(request.url.path) == "/":
            return httpx.Response(200, content=b"hello")
        return httpx.Response(404)

    bundle = await run_probes(
        "http://safe.test",
        tier=Tier.ACTIVE,
        resolver=_fake_resolver,
        transport=httpx.MockTransport(handler),
    )

    assert bundle.paths is not None
    assert any(d.path == "/.git/config" for d in bundle.paths.detected)
