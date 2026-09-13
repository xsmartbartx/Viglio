from __future__ import annotations

from collections.abc import Iterator

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from vigilo_persistence.testing import temporary_schema

import vigilo_identity.orm  # noqa: F401
import vigilo_orchestrator.orm  # noqa: F401
import vigilo_project.orm  # noqa: F401
import vigilo_security.orm  # noqa: F401
from vigilo_api.main import app


@pytest_asyncio.fixture
async def schema():
    async with temporary_schema():
        yield


@pytest.fixture
def client(schema) -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
