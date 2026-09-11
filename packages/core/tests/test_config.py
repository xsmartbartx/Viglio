import json

import pytest
from vigilo_core.config import config
from vigilo_core.errors import StructuredError


@pytest.fixture(autouse=True)
def _clear_config_cache():
    config.cache_clear()
    yield
    config.cache_clear()


def test_config_loads_brand_from_repo_brand_config_json(monkeypatch):
    monkeypatch.delenv("VIGILO_BRAND_CONFIG_PATH", raising=False)
    monkeypatch.setenv("ENV", "test")

    cfg = config()

    assert cfg.env == "test"
    assert cfg.brand.brand.name == "Vigilo"
    assert cfg.brand.brand.slug == "vigilo"


def test_config_reads_infra_settings_from_environment(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://x/y")
    monkeypatch.setenv("REDIS_URL", "redis://x")

    cfg = config()

    assert cfg.database_url == "postgresql://x/y"
    assert cfg.redis_url == "redis://x"


def test_config_honors_explicit_brand_config_path_override(tmp_path, monkeypatch):
    custom = tmp_path / "brand.config.json"
    custom.write_text(
        json.dumps(
            {
                "brand": {
                    "name": "Other",
                    "legalName": "Other",
                    "slug": "other",
                    "domain": "other.io",
                    "tagline": "x",
                    "shortDescription": "x",
                    "supportEmail": "a@other.io",
                    "abuseEmail": "a@other.io",
                    "securityEmail": "a@other.io",
                }
            }
        )
    )
    monkeypatch.setenv("VIGILO_BRAND_CONFIG_PATH", str(custom))

    cfg = config()

    assert cfg.brand.brand.name == "Other"


def test_config_raises_structured_error_for_missing_brand_config(tmp_path, monkeypatch):
    monkeypatch.setenv("VIGILO_BRAND_CONFIG_PATH", str(tmp_path / "missing.json"))

    with pytest.raises(StructuredError):
        config()
