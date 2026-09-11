from __future__ import annotations

from fastapi import FastAPI

from vigilo_core.config import config

app = FastAPI(
    title="Vigilo API",
    description="Control-plane HTTP surface. Phase 0: health/version bootstrap only.",
    version="0.1.0",
)


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
