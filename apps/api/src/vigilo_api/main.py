from __future__ import annotations

from fastapi import FastAPI
from vigilo_core.config import config
from vigilo_core.errors import StructuredError

from vigilo_api.errors import handle_structured_error
from vigilo_api.routers import accounts, scans, targets

app = FastAPI(
    title="Vigilo API",
    description="Control-plane HTTP surface.",
    version="0.1.0",
)

app.add_exception_handler(StructuredError, handle_structured_error)

app.include_router(scans.router)
app.include_router(targets.router)
app.include_router(accounts.router)


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
