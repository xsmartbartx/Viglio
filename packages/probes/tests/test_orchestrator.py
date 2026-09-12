import httpx

from vigilo_probes.orchestrator import run_probes

_FAKE_DNS = {"safe.test": ["93.184.216.34"]}


def _fake_resolver(hostname: str) -> list[str]:
    return _FAKE_DNS[hostname]


def _handler(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, headers=[("server", "cloudflare")], content=b"hello")


async def test_run_probes_skips_tls_for_http_scheme(monkeypatch):
    import vigilo_probes.orchestrator as orch_module

    async def fake_run_http(url, resolver=None):
        from vigilo_core.evidence import HttpObservation

        return HttpObservation(
            url="http://safe.test/", status_code=200, headers={"server": "cloudflare"}
        )

    monkeypatch.setattr(orch_module, "run_http", fake_run_http)

    bundle = await run_probes("http://safe.test", resolver=_fake_resolver)

    assert bundle.tls is None
    assert bundle.http.status_code == 200
    assert bundle.fingerprint is not None
    assert "cloudflare" in bundle.fingerprint.hosting_signals
    assert bundle.target_origin == "http://safe.test"
