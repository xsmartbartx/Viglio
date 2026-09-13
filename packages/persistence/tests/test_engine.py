from __future__ import annotations

import pytest

from vigilo_core.errors import ErrorCode, StructuredError
from vigilo_persistence.engine import _to_asyncpg_url


def test_rewrites_plain_postgresql_scheme_to_asyncpg() -> None:
    assert _to_asyncpg_url("postgresql://u:p@host:5432/db") == "postgresql+asyncpg://u:p@host:5432/db"


def test_leaves_an_already_asyncpg_url_unchanged() -> None:
    url = "postgresql+asyncpg://u:p@host:5432/db"
    assert _to_asyncpg_url(url) == url


def test_rejects_an_unrecognized_scheme() -> None:
    with pytest.raises(StructuredError) as exc_info:
        _to_asyncpg_url("mysql://u:p@host:3306/db")
    assert exc_info.value.code == ErrorCode.CONFIGURATION_ERROR
