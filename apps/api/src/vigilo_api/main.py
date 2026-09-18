from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from vigilo_api.errors import handle_structured_error
from vigilo_api.routers import (
    accounts,
    api_keys,
    badge,
    billing,
    branding,
    monitors,
    public_api,
    reports,
    scans,
    share_links,
    targets,
)
from vigilo_core.config import config
from vigilo_core.errors import StructuredError

app = FastAPI(
    title="Vigilo API",
    description="Control-plane HTTP surface.",
    version="0.1.0",
)

app.add_exception_handler(StructuredError, handle_structured_error)

# apps/web is the first browser client to ever call this API (Phase 4) — the
# PDF-export/report/share-link routes are called directly from client
# components. Conditional on WEB_APP_URL being set, same "works without it"
# resilience pattern as Clerk/Postmark's config.
_web_app_url = config().web_app_url
if _web_app_url:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[_web_app_url],
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(scans.router)
app.include_router(targets.router)
app.include_router(accounts.router)
app.include_router(reports.router)
app.include_router(share_links.router)
app.include_router(billing.router)
app.include_router(billing.plans_router)
app.include_router(monitors.router)
app.include_router(badge.router)
app.include_router(api_keys.router)
app.include_router(branding.router)
app.include_router(public_api.router)


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/version")
def version() -> dict[str, str]:
    cfg = config()
    return {
        "product": cfg.brand.brand.name,
        "env": cfg.env,
        "api_version": app.version,
        "registry_version": "unreleased",
    }
