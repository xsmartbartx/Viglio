"""Configuration and brand token loading. `config()` is the single entry point
every module uses to read brand identity and infrastructure settings
(docs/modules.md §1). Brand identity is always sourced from `brand.config.json`
— see README.md "Branding": nothing hardcodes the product name in source.
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel, Field

from vigilo_core.errors import ErrorCode, StructuredError

# Loads .env into the process environment if present, without overriding
# variables the environment (or CI) has already set. Phase 0-2 never needed
# this — nothing read DATABASE_URL/REDIS_URL/etc. at runtime. Phase 3's
# control plane does, so `uv run uvicorn ...` / `uv run arq ...` following
# README's "cp .env.example .env" instructions now actually picks it up.
load_dotenv()


class BrandTheme(BaseModel):
    colorPrimary: str
    colorAccent: str
    colorCritical: str
    colorHigh: str
    colorMedium: str
    colorLow: str
    colorPass: str
    fontSans: str
    fontMono: str


class Brand(BaseModel):
    name: str
    legalName: str
    slug: str
    domain: str
    tagline: str
    shortDescription: str
    supportEmail: str
    abuseEmail: str
    securityEmail: str


class BrandConfig(BaseModel):
    brand: Brand
    namespaces: dict[str, str] = Field(default_factory=dict)
    theme: BrandTheme | None = None


class Config(BaseModel):
    env: str = "development"
    brand: BrandConfig
    database_url: str | None = None
    redis_url: str | None = None
    object_store_endpoint: str | None = None
    object_store_access_key: str | None = None
    object_store_secret_key: str | None = None
    object_store_bucket: str | None = None
    clerk_secret_key: str | None = None
    clerk_jwks_url: str | None = None
    postmark_server_token: str | None = None
    mail_from_address: str | None = None


def _default_brand_config_path() -> Path:
    override = os.environ.get("VIGILO_BRAND_CONFIG_PATH")
    if override:
        return Path(override).expanduser().resolve()

    for parent in Path(__file__).resolve().parents:
        candidate = parent / "brand.config.json"
        if candidate.is_file():
            return candidate

    raise StructuredError(
        ErrorCode.CONFIGURATION_ERROR,
        "brand.config.json not found in any parent directory; "
        "set VIGILO_BRAND_CONFIG_PATH explicitly",
    )


def _load_brand_config(path: Path) -> BrandConfig:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise StructuredError(
            ErrorCode.CONFIGURATION_ERROR, f"brand config not found at {path}"
        ) from exc
    except json.JSONDecodeError as exc:
        raise StructuredError(
            ErrorCode.CONFIGURATION_ERROR, f"brand config at {path} is not valid JSON"
        ) from exc

    return BrandConfig.model_validate(raw)


@lru_cache(maxsize=1)
def config() -> Config:
    """Load and cache process configuration. Call `config.cache_clear()` in
    tests that need to reload after changing environment variables."""
    brand_path = _default_brand_config_path()
    brand = _load_brand_config(brand_path)

    return Config(
        env=os.environ.get("ENV", "development"),
        brand=brand,
        database_url=os.environ.get("DATABASE_URL"),
        redis_url=os.environ.get("REDIS_URL"),
        object_store_endpoint=os.environ.get("OBJECT_STORE_ENDPOINT"),
        object_store_access_key=os.environ.get("OBJECT_STORE_ACCESS_KEY"),
        object_store_secret_key=os.environ.get("OBJECT_STORE_SECRET_KEY"),
        object_store_bucket=os.environ.get("OBJECT_STORE_BUCKET"),
        clerk_secret_key=os.environ.get("CLERK_SECRET_KEY"),
        clerk_jwks_url=os.environ.get("CLERK_JWKS_URL"),
        postmark_server_token=os.environ.get("POSTMARK_SERVER_TOKEN"),
        mail_from_address=os.environ.get("MAIL_FROM_ADDRESS"),
    )
