"""Evidence-bundle object storage: MinIO locally, S3-compatible in production
(docs/architecture.md §5). `boto3` (sync) wrapped in `asyncio.to_thread`,
matching the existing convention for blocking calls inside async code
(`packages/probes/src/vigilo_probes/orchestrator.py`'s TLS probing) rather
than adding `aioboto3` as a second, less-common async S3 client.

Neither Phase 3 exit criterion strictly needs this (the emailed report reads
from `Scan`/`Finding` rows, not the bundle) — it's the first thing to cut if
the phase needs to shrink further, per the plan's scope-trim notes. Kept
because the bucket already exists (`docker-compose.yml`'s `minio-init`
service) and the code is small.
"""

from __future__ import annotations

import asyncio
from functools import lru_cache

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from vigilo_core.config import config
from vigilo_core.errors import ErrorCode, StructuredError
from vigilo_integrations.errors import ObjectStoreError

_KEY_PREFIX = "evidence/"
_REPORT_KEY_PREFIX = "reports/"


@lru_cache(maxsize=1)
def _client():
    cfg = config()
    if not cfg.object_store_endpoint or not cfg.object_store_bucket:
        raise StructuredError(ErrorCode.CONFIGURATION_ERROR, "object storage is not configured")
    return boto3.client(
        "s3",
        endpoint_url=cfg.object_store_endpoint,
        aws_access_key_id=cfg.object_store_access_key,
        aws_secret_access_key=cfg.object_store_secret_key,
        region_name="us-east-1",
    )


def _key(bundle_id: str) -> str:
    return f"{_KEY_PREFIX}{bundle_id}.json"


def _report_key(report_id: str) -> str:
    return f"{_REPORT_KEY_PREFIX}{report_id}.pdf"


def _put_sync(key: str, content: bytes) -> None:
    cfg = config()
    _client().put_object(Bucket=cfg.object_store_bucket, Key=key, Body=content)


def _get_sync(key: str) -> bytes:
    cfg = config()
    obj = _client().get_object(Bucket=cfg.object_store_bucket, Key=key)
    return obj["Body"].read()


async def put_evidence_bundle(bundle_id: str, content: bytes) -> None:
    try:
        await asyncio.to_thread(_put_sync, _key(bundle_id), content)
    except (BotoCoreError, ClientError) as exc:
        raise ObjectStoreError("failed to store evidence bundle", bundle_id=bundle_id) from exc


async def get_evidence_bundle(bundle_id: str) -> bytes:
    try:
        return await asyncio.to_thread(_get_sync, _key(bundle_id))
    except (BotoCoreError, ClientError) as exc:
        raise ObjectStoreError("failed to fetch evidence bundle", bundle_id=bundle_id) from exc


async def put_report_pdf(report_id: str, content: bytes) -> None:
    try:
        await asyncio.to_thread(_put_sync, _report_key(report_id), content)
    except (BotoCoreError, ClientError) as exc:
        raise ObjectStoreError("failed to store report pdf", report_id=report_id) from exc


async def get_report_pdf(report_id: str) -> bytes:
    try:
        return await asyncio.to_thread(_get_sync, _report_key(report_id))
    except (BotoCoreError, ClientError) as exc:
        raise ObjectStoreError("failed to fetch report pdf", report_id=report_id) from exc
