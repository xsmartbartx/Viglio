from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from vigilo_identity.repository import (
    get_account_by_id,
    get_or_create_account,
    get_subscription_by_account,
    upsert_subscription,
)

_PERIOD_END = datetime(2026, 10, 16, tzinfo=UTC)


async def test_get_subscription_by_account_returns_none_when_none_exists(
    db_session: AsyncSession,
) -> None:
    account = await get_or_create_account(db_session, email="nosub@example.com")

    assert await get_subscription_by_account(db_session, account.id) is None


async def test_upsert_subscription_creates_a_row_and_cascades_plan_id_to_the_account(
    db_session: AsyncSession,
) -> None:
    account = await get_or_create_account(db_session, email="upgrade@example.com")

    subscription = await upsert_subscription(
        db_session,
        account_id=account.id,
        plan_id="builder",
        status="active",
        provider="paddle",
        provider_subscription_id="sub_001",
        current_period_end=_PERIOD_END,
    )

    assert subscription.plan_id == "builder"
    assert subscription.status == "active"

    reloaded = await get_subscription_by_account(db_session, account.id)
    assert reloaded is not None
    assert reloaded.provider_subscription_id == "sub_001"

    updated_account = await get_account_by_id(db_session, account.id)
    assert updated_account is not None
    assert updated_account.plan_id == "builder"


async def test_upsert_subscription_replays_the_same_provider_id_as_an_update_not_a_duplicate(
    db_session: AsyncSession,
) -> None:
    account = await get_or_create_account(db_session, email="replay@example.com")
    await upsert_subscription(
        db_session,
        account_id=account.id,
        plan_id="builder",
        status="active",
        provider="paddle",
        provider_subscription_id="sub_002",
        current_period_end=_PERIOD_END,
    )

    await upsert_subscription(
        db_session,
        account_id=account.id,
        plan_id="studio",
        status="active",
        provider="paddle",
        provider_subscription_id="sub_002",
        current_period_end=_PERIOD_END,
    )

    reloaded = await get_subscription_by_account(db_session, account.id)
    assert reloaded is not None
    assert reloaded.plan_id == "studio"

    updated_account = await get_account_by_id(db_session, account.id)
    assert updated_account is not None
    assert updated_account.plan_id == "studio"


async def test_a_canceled_subscription_resets_the_account_to_free_not_the_canceled_plan(
    db_session: AsyncSession,
) -> None:
    account = await get_or_create_account(db_session, email="cancel@example.com")
    await upsert_subscription(
        db_session,
        account_id=account.id,
        plan_id="studio",
        status="active",
        provider="paddle",
        provider_subscription_id="sub_003",
        current_period_end=_PERIOD_END,
    )

    await upsert_subscription(
        db_session,
        account_id=account.id,
        plan_id="studio",
        status="canceled",
        provider="paddle",
        provider_subscription_id="sub_003",
        current_period_end=_PERIOD_END,
    )

    updated_account = await get_account_by_id(db_session, account.id)
    assert updated_account is not None
    assert updated_account.plan_id == "free"


async def test_get_subscription_by_account_returns_the_most_recently_created_row(
    db_session: AsyncSession,
) -> None:
    account = await get_or_create_account(db_session, email="multi@example.com")
    await upsert_subscription(
        db_session,
        account_id=account.id,
        plan_id="builder",
        status="active",
        provider="paddle",
        provider_subscription_id="sub_004",
        current_period_end=_PERIOD_END,
    )
    # Commit to close out the transaction Postgres' now() is pinned to —
    # otherwise both rows land in the same still-open transaction and get
    # an identical created_at, making the ordering this test checks
    # non-deterministic.
    await db_session.commit()
    await upsert_subscription(
        db_session,
        account_id=account.id,
        plan_id="studio",
        status="active",
        provider="paddle",
        provider_subscription_id="sub_005",
        current_period_end=_PERIOD_END,
    )

    latest = await get_subscription_by_account(db_session, account.id)
    assert latest is not None
    assert latest.provider_subscription_id == "sub_005"
