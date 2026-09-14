"""render_pdf(): Playwright navigates the LIVE `apps/web` report page and
prints it — not a second, Python-templated HTML system. Per the Prooflight
doc's own framing for this artefact ("Headless render of the web report...
one layout source of truth"), building a parallel Python/Jinja2 template
that must be kept visually in sync with the React page is exactly the kind
of drift that framing warns against.

This is safe with no auth-token-minting complexity: `/reports/{scan_id}` is
unauthenticated by design (same posture as `GET /v1/scans/{id}` since
Phase 3), so Playwright just navigates a public URL.

The real, worth-stating tradeoff: `apps/scanner`'s worker process needs
outbound network access to wherever `apps/web` runs (`WEB_APP_URL`) — see
the ADR-0002 Phase 4 addendum.

`pdf_renderer` is the same dependency-injection seam used everywhere else
in this codebase (`resolver=`, `transport=`, `get_signing_key=`) — tests
inject a fake one and never launch a real browser.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from vigilo_core.config import config

from vigilo_reporting.errors import PdfRenderError

PdfRenderer = Callable[[str], Awaitable[bytes]]


async def _default_pdf_renderer(url: str) -> bytes:
    from playwright.async_api import async_playwright

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch()
        try:
            page = await browser.new_page()
            await page.goto(url, wait_until="networkidle")
            return await page.pdf(format="A4", print_background=True)
        finally:
            await browser.close()


async def render_pdf(scan_job_id: str, pdf_renderer: PdfRenderer | None = None) -> bytes:
    cfg = config()
    if not cfg.web_app_url:
        raise PdfRenderError("WEB_APP_URL is not set")

    render = pdf_renderer or _default_pdf_renderer
    url = f"{cfg.web_app_url}/reports/{scan_job_id}?print=1"

    try:
        return await render(url)
    except PdfRenderError:
        raise
    except Exception as exc:
        raise PdfRenderError("PDF render failed", url=url) from exc
