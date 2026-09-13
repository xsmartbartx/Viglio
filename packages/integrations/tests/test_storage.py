"""Integration test against the real local MinIO (docker-compose's `minio`
service, bucket pre-created by `minio-init`) — matches the plan's CI
approach of a real service container rather than mocking `boto3`.
"""

from __future__ import annotations

import uuid

import pytest

from vigilo_core.config import config
from vigilo_integrations.storage import get_evidence_bundle, put_evidence_bundle

pytestmark = pytest.mark.skipif(
    not config().object_store_endpoint, reason="OBJECT_STORE_ENDPOINT not configured"
)


async def test_round_trips_a_bundle_through_object_storage():
    bundle_id = f"test-{uuid.uuid4()}"
    content = b'{"origin": "https://example.com"}'

    await put_evidence_bundle(bundle_id, content)
    fetched = await get_evidence_bundle(bundle_id)

    assert fetched == content
