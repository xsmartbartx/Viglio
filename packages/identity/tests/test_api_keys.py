from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from vigilo_identity.repository import (
    count_api_keys_for_account,
    create_api_key,
    get_api_key_by_hash,
    get_or_create_account,
    hash_api_key,
    list_api_keys_for_account,
    mark_api_key_used,
    revoke_api_key,
)


async def test_create_api_key_returns_the_plaintext_once(db_session: AsyncSession) -> None:
    account = await get_or_create_account(db_session, email="keyowner@example.com")

    api_key, raw_key = await create_api_key(
        db_session, account.id, "CI pipeline", ["scan:run", "scan:read"]
    )

    assert raw_key.startswith("vglo_")
    assert api_key.prefix == raw_key[:12]
    assert api_key.scopes == ["scan:run", "scan:read"]
    assert api_key.revoked_at is None


async def test_get_api_key_by_hash_finds_the_key_by_its_hash(db_session: AsyncSession) -> None:
    account = await get_or_create_account(db_session, email="keylookup@example.com")
    api_key, raw_key = await create_api_key(db_session, account.id, "test key", ["scan:read"])

    found = await get_api_key_by_hash(db_session, hash_api_key(raw_key))

    assert found is not None
    assert found.id == api_key.id


async def test_get_api_key_by_hash_returns_none_for_an_unknown_hash(
    db_session: AsyncSession,
) -> None:
    assert await get_api_key_by_hash(db_session, hash_api_key("not-a-real-key")) is None


async def test_list_api_keys_for_account_returns_most_recent_first(
    db_session: AsyncSession,
) -> None:
    account = await get_or_create_account(db_session, email="keylist@example.com")
    first, _ = await create_api_key(db_session, account.id, "first", ["scan:read"])
    await db_session.commit()
    second, _ = await create_api_key(db_session, account.id, "second", ["scan:read"])

    keys = await list_api_keys_for_account(db_session, account.id)

    assert [k.id for k in keys] == [second.id, first.id]


async def test_revoke_api_key_sets_revoked_at(db_session: AsyncSession) -> None:
    account = await get_or_create_account(db_session, email="keyrevoke@example.com")
    api_key, _ = await create_api_key(db_session, account.id, "to revoke", ["scan:read"])

    revoked = await revoke_api_key(db_session, api_key.id)

    assert revoked is not None
    assert revoked.revoked_at is not None


async def test_revoke_an_unknown_api_key_returns_none(db_session: AsyncSession) -> None:
    import uuid

    assert await revoke_api_key(db_session, uuid.uuid4()) is None


async def test_mark_api_key_used_sets_last_used_at(db_session: AsyncSession) -> None:
    account = await get_or_create_account(db_session, email="keyused@example.com")
    api_key, _ = await create_api_key(db_session, account.id, "used key", ["scan:read"])
    now = datetime.now(UTC)

    await mark_api_key_used(db_session, api_key.id, now)

    keys = await list_api_keys_for_account(db_session, account.id)
    assert keys[0].last_used_at is not None


async def test_count_api_keys_for_account_excludes_revoked_keys(db_session: AsyncSession) -> None:
    account = await get_or_create_account(db_session, email="keycount@example.com")
    active, _ = await create_api_key(db_session, account.id, "active", ["scan:read"])
    revoked, _ = await create_api_key(db_session, account.id, "revoked", ["scan:read"])
    await revoke_api_key(db_session, revoked.id)

    assert await count_api_keys_for_account(db_session, account.id) == 1
