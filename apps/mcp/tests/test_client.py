from __future__ import annotations

import httpx
import pytest

from vigilo_mcp.client import (
    VigiloApiError,
    get_scan_findings,
    get_scan_report,
    get_scan_status,
    submit_scan,
)


@pytest.fixture(autouse=True)
def _configured(monkeypatch):
    monkeypatch.setenv("VIGILO_API_KEY", "vglo_test_key")
    monkeypatch.setenv("VIGILO_API_BASE_URL", "https://vigilo.example.com")
    yield


async def test_submit_scan_sends_the_bearer_token_and_body():
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["auth"] = request.headers["Authorization"]
        captured["body"] = request.content.decode()
        return httpx.Response(202, json={"scan_job_id": "abc", "status": "authorized"})

    result = await submit_scan(
        "https://example.com", transport=httpx.MockTransport(handler)
    )

    assert captured["url"] == "https://vigilo.example.com/public/v1/scans"
    assert captured["auth"] == "Bearer vglo_test_key"
    assert "https://example.com" in captured["body"]
    assert result["scan_job_id"] == "abc"


async def test_get_scan_status_returns_the_parsed_body():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"status": "complete"})

    result = await get_scan_status("abc", transport=httpx.MockTransport(handler))
    assert result["status"] == "complete"


async def test_get_scan_report_returns_the_parsed_body():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"score": 92.0, "findings": []})

    result = await get_scan_report("abc", transport=httpx.MockTransport(handler))
    assert result["score"] == 92.0


async def test_get_scan_findings_returns_a_list():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[{"check_id": "VG-HDR-001"}])

    result = await get_scan_findings("abc", transport=httpx.MockTransport(handler))
    assert result == [{"check_id": "VG-HDR-001"}]


async def test_a_non_2xx_response_raises_vigilo_api_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"detail": "scan not found"})

    with pytest.raises(VigiloApiError) as exc_info:
        await get_scan_status("unknown", transport=httpx.MockTransport(handler))

    assert exc_info.value.status_code == 404


async def test_missing_api_key_raises_a_clear_error(monkeypatch):
    monkeypatch.delenv("VIGILO_API_KEY", raising=False)

    with pytest.raises(RuntimeError, match="VIGILO_API_KEY"):
        await get_scan_status("abc")
