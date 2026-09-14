from __future__ import annotations

import pytest
from vigilo_core.config import config

from vigilo_reporting.errors import PdfRenderError
from vigilo_reporting.pdf import render_pdf


@pytest.fixture(autouse=True)
def _web_app_url_configured(monkeypatch):
    monkeypatch.setenv("WEB_APP_URL", "http://localhost:3000")
    config.cache_clear()
    yield
    config.cache_clear()


async def test_render_pdf_navigates_the_expected_report_url():
    captured = {}

    async def fake_renderer(url: str) -> bytes:
        captured["url"] = url
        return b"%PDF-1.4 fake"

    pdf_bytes = await render_pdf("scan-123", pdf_renderer=fake_renderer)

    assert pdf_bytes == b"%PDF-1.4 fake"
    assert captured["url"] == "http://localhost:3000/reports/scan-123?print=1"


async def test_raises_when_web_app_url_is_not_configured(monkeypatch):
    monkeypatch.delenv("WEB_APP_URL", raising=False)
    config.cache_clear()

    async def fake_renderer(url: str) -> bytes:
        return b"unused"

    with pytest.raises(PdfRenderError):
        await render_pdf("scan-123", pdf_renderer=fake_renderer)


async def test_wraps_a_renderer_failure_in_pdf_render_error():
    async def failing_renderer(url: str) -> bytes:
        raise RuntimeError("navigation timeout")

    with pytest.raises(PdfRenderError):
        await render_pdf("scan-123", pdf_renderer=failing_renderer)
