from __future__ import annotations

import uuid

import pytest_asyncio
from redis.asyncio import Redis

from vigilo_core.config import config
from vigilo_security.rate_limit import check_rate


@pytest_asyncio.fixture
async def redis():
    client = Redis.from_url(config().redis_url)
    try:
        yield client
    finally:
        await client.aclose()


def _key() -> str:
    return f"test:rate_limit:{uuid.uuid4()}"


async def test_check_rate_allows_under_the_limit(redis: Redis) -> None:
    key = _key()
    decision = await check_rate(redis, key, limit=5, window_seconds=60)

    assert decision.allowed is True
    assert decision.retry_after_seconds is None


async def test_check_rate_allows_exactly_at_the_limit(redis: Redis) -> None:
    key = _key()
    for _ in range(5):
        decision = await check_rate(redis, key, limit=5, window_seconds=60)
    assert decision.allowed is True


async def test_check_rate_denies_over_the_limit(redis: Redis) -> None:
    key = _key()
    for _ in range(5):
        await check_rate(redis, key, limit=5, window_seconds=60)

    decision = await check_rate(redis, key, limit=5, window_seconds=60)

    assert decision.allowed is False
    assert decision.retry_after_seconds is not None
    assert decision.retry_after_seconds > 0


async def test_check_rate_is_unlimited_for_a_none_limit(redis: Redis) -> None:
    key = _key()
    for _ in range(1000):
        decision = await check_rate(redis, key, limit=None, window_seconds=60)
    assert decision.allowed is True
    assert decision.retry_after_seconds is None


async def test_check_rate_tracks_separate_keys_independently(redis: Redis) -> None:
    key_a, key_b = _key(), _key()
    for _ in range(5):
        await check_rate(redis, key_a, limit=5, window_seconds=60)

    decision_a = await check_rate(redis, key_a, limit=5, window_seconds=60)
    decision_b = await check_rate(redis, key_b, limit=5, window_seconds=60)

    assert decision_a.allowed is False
    assert decision_b.allowed is True
