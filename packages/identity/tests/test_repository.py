from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from vigilo_identity.repository import (
    get_account_by_clerk_id,
    get_account_by_email,
    get_account_by_id,
    get_or_create_account,
)


async def test_creates_an_anonymous_account_from_email_alone(db_session: AsyncSession) -> None:
    account = await get_or_create_account(db_session, email="scan@example.com")

    assert account.status == "anonymous"
    assert account.clerk_user_id is None
    assert account.email == "scan@example.com"


async def test_creates_an_active_account_when_a_clerk_id_is_supplied(
    db_session: AsyncSession,
) -> None:
    account = await get_or_create_account(
        db_session, email="owner@example.com", clerk_user_id="user_abc123"
    )

    assert account.status == "active"
    assert account.clerk_user_id == "user_abc123"


async def test_repeated_calls_with_the_same_email_return_the_same_account(
    db_session: AsyncSession,
) -> None:
    first = await get_or_create_account(db_session, email="scan@example.com")
    second = await get_or_create_account(db_session, email="scan@example.com")

    assert first.id == second.id


async def test_signing_in_later_attaches_the_clerk_id_to_the_existing_anonymous_account(
    db_session: AsyncSession,
) -> None:
    anonymous = await get_or_create_account(db_session, email="claim@example.com")
    assert anonymous.status == "anonymous"

    claimed = await get_or_create_account(
        db_session, email="claim@example.com", clerk_user_id="user_claim1"
    )

    assert claimed.id == anonymous.id
    assert claimed.status == "active"
    assert claimed.clerk_user_id == "user_claim1"


async def test_an_already_linked_account_is_not_relinked_to_a_different_clerk_id(
    db_session: AsyncSession,
) -> None:
    first = await get_or_create_account(
        db_session, email="stable@example.com", clerk_user_id="user_first"
    )
    second = await get_or_create_account(
        db_session, email="stable@example.com", clerk_user_id="user_second"
    )

    assert second.id == first.id
    assert second.clerk_user_id == "user_first"


async def test_get_account_by_id_returns_none_for_an_unknown_id(db_session: AsyncSession) -> None:
    import uuid

    assert await get_account_by_id(db_session, uuid.uuid4()) is None


async def test_get_account_by_clerk_id_finds_a_linked_account(db_session: AsyncSession) -> None:
    created = await get_or_create_account(
        db_session, email="lookup@example.com", clerk_user_id="user_lookup"
    )

    found = await get_account_by_clerk_id(db_session, "user_lookup")

    assert found is not None
    assert found.id == created.id


async def test_get_account_by_email_finds_an_existing_account(db_session: AsyncSession) -> None:
    created = await get_or_create_account(db_session, email="byemail@example.com")

    found = await get_account_by_email(db_session, "byemail@example.com")

    assert found is not None
    assert found.id == created.id


async def test_get_account_by_email_returns_none_for_an_unknown_email(
    db_session: AsyncSession,
) -> None:
    assert await get_account_by_email(db_session, "never-signed-up@example.com") is None
