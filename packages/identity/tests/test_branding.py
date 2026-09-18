from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from vigilo_identity.repository import (
    get_branding_profile,
    get_or_create_account,
    upsert_branding_profile,
)


async def test_get_branding_profile_returns_none_when_none_exists(
    db_session: AsyncSession,
) -> None:
    account = await get_or_create_account(db_session, email="nobrand@example.com")
    assert await get_branding_profile(db_session, account.id) is None


async def test_upsert_branding_profile_creates_a_profile(db_session: AsyncSession) -> None:
    account = await get_or_create_account(db_session, email="brandnew@example.com")

    profile = await upsert_branding_profile(
        db_session,
        account.id,
        logo_url="https://example.com/logo.png",
        primary_color="#112233",
        footer_text="Provided by Acme Security",
        custom_domain="reports.acme.example.com",
    )

    assert profile.logo_url == "https://example.com/logo.png"
    assert profile.primary_color == "#112233"

    fetched = await get_branding_profile(db_session, account.id)
    assert fetched is not None
    assert fetched.id == profile.id


async def test_upsert_branding_profile_updates_the_existing_row_not_a_duplicate(
    db_session: AsyncSession,
) -> None:
    account = await get_or_create_account(db_session, email="brandupdate@example.com")
    first = await upsert_branding_profile(db_session, account.id, logo_url="https://a.example.com/logo.png")

    second = await upsert_branding_profile(db_session, account.id, logo_url="https://b.example.com/logo.png")

    assert second.id == first.id
    assert second.logo_url == "https://b.example.com/logo.png"


async def test_upsert_branding_profile_is_a_partial_update(db_session: AsyncSession) -> None:
    account = await get_or_create_account(db_session, email="brandpartial@example.com")
    await upsert_branding_profile(
        db_session,
        account.id,
        logo_url="https://example.com/logo.png",
        primary_color="#112233",
    )

    updated = await upsert_branding_profile(
        db_session, account.id, footer_text="Provided by Acme Security"
    )

    assert updated.footer_text == "Provided by Acme Security"
    assert updated.logo_url == "https://example.com/logo.png"
    assert updated.primary_color == "#112233"
