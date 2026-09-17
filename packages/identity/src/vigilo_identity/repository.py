"""Account repository. Every function takes an already-open `AsyncSession`
rather than opening its own — the caller (an API handler or ARQ job body,
via `vigilo_persistence.session_scope`) controls the transaction boundary,
matching the pattern `vigilo_security.audit.audit()` uses for the same reason
(ADR-0003: a decision and everything it depends on commit together).
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from vigilo_identity.models import Account, ApiKey, BrandingProfile, Subscription
from vigilo_identity.orm import AccountRow, ApiKeyRow, BrandingProfileRow, SubscriptionRow


async def get_account_by_id(session: AsyncSession, account_id: object) -> Account | None:
    row = await session.get(AccountRow, account_id)
    return Account.model_validate(row) if row else None


async def get_account_by_clerk_id(session: AsyncSession, clerk_user_id: str) -> Account | None:
    stmt = select(AccountRow).where(AccountRow.clerk_user_id == clerk_user_id)
    result = await session.execute(stmt)
    row = result.scalar_one_or_none()
    return Account.model_validate(row) if row else None


async def get_account_by_email(session: AsyncSession, email: str) -> Account | None:
    """Read-only — never creates. Used where a caller needs to know whether
    a *returning* submitter already exists without the side effect of
    `get_or_create_account`, e.g. `POST /v1/scans` looking up a returning
    submitter's real verification state before deciding whether a denied
    request should be allowed to leave no account/target row behind."""
    stmt = select(AccountRow).where(AccountRow.email == email)
    result = await session.execute(stmt)
    row = result.scalar_one_or_none()
    return Account.model_validate(row) if row else None


async def get_or_create_account(
    session: AsyncSession, email: str, clerk_user_id: str | None = None
) -> Account:
    """Look up an account by email; create one if none exists.

    If a Clerk id is supplied and the matching-by-email row is still
    anonymous (created earlier by a free scan, never signed in), attach the
    Clerk id and promote it to `active` in place — this is what makes the
    anonymous free-scan path (exit criterion a) and the authenticated
    ownership-verification path (exit criterion b) converge on one `Account`
    row rather than creating a duplicate the day someone signs up.
    """
    result = await session.execute(select(AccountRow).where(AccountRow.email == email))
    row = result.scalar_one_or_none()

    if row is None:
        row = AccountRow(
            email=email,
            clerk_user_id=clerk_user_id,
            status="active" if clerk_user_id else "anonymous",
        )
        session.add(row)
        await session.flush()
        return Account.model_validate(row)

    if clerk_user_id and row.clerk_user_id is None:
        row.clerk_user_id = clerk_user_id
        row.status = "active"
        await session.flush()

    return Account.model_validate(row)


async def get_subscription_by_account(
    session: AsyncSession, account_id: uuid.UUID
) -> Subscription | None:
    """The most recent subscription row for this account, if more than one
    exists — a provider issues a new `provider_subscription_id` on plan
    change/renewal, so rows accumulate over time rather than being
    updated in place."""
    stmt = (
        select(SubscriptionRow)
        .where(SubscriptionRow.account_id == account_id)
        .order_by(SubscriptionRow.created_at.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    row = result.scalar_one_or_none()
    return Subscription.model_validate(row) if row else None


async def upsert_subscription(
    session: AsyncSession,
    account_id: uuid.UUID,
    plan_id: str,
    status: str,
    provider: str,
    provider_subscription_id: str,
    current_period_end: datetime | None,
) -> Subscription:
    """Keyed on `provider_subscription_id` — a webhook replaying the same
    event, or a later status update for the same subscription, updates the
    existing row rather than creating a duplicate. Cascades `AccountRow
    .plan_id` in the same flush, identical to `mark_proof_verified()`
    cascading `Target.verification_status`
    (`packages/project/src/vigilo_project/repository.py`)."""
    result = await session.execute(
        select(SubscriptionRow).where(
            SubscriptionRow.provider_subscription_id == provider_subscription_id
        )
    )
    row = result.scalar_one_or_none()

    if row is None:
        row = SubscriptionRow(
            account_id=account_id,
            plan_id=plan_id,
            status=status,
            provider=provider,
            provider_subscription_id=provider_subscription_id,
            current_period_end=current_period_end,
        )
        session.add(row)
    else:
        row.plan_id = plan_id
        row.status = status
        row.current_period_end = current_period_end

    # A canceled/non-active subscription must NOT leave the account holding
    # its paid entitlements forever — entitlements() only ever looks at
    # Account.plan_id, so a cancellation has to actually reset it to "free"
    # here, not just record status="canceled" on a row nothing re-reads.
    account_row = await session.get(AccountRow, account_id)
    if account_row is not None:
        account_row.plan_id = plan_id if status == "active" else "free"

    await session.flush()
    return Subscription.model_validate(row)


def hash_api_key(raw_key: str) -> str:
    """The one place a presented API key is turned into its lookup hash —
    `create_api_key()` below and `apps/api`'s verification-time lookup
    both call this, so there is exactly one hashing implementation to keep
    in sync. Matches `vigilo_orchestrator.reports`'s own share-link
    token-hashing precedent, made public here since hashing and lookup
    live in different packages for API keys (creation in `apps/api`'s
    session-authenticated router, verification in its API-key auth
    dependency)."""
    return hashlib.sha256(raw_key.encode()).hexdigest()


async def create_api_key(
    session: AsyncSession, account_id: uuid.UUID, name: str, scopes: list[str]
) -> tuple[ApiKey, str]:
    """Returns `(api_key, plaintext_key)` — the plaintext is returned
    exactly once, at creation, and never persisted (`key_hash` only),
    matching `create_share_link()`'s exact token pattern."""
    raw_key = f"vglo_{secrets.token_urlsafe(32)}"
    row = ApiKeyRow(
        account_id=account_id,
        name=name,
        prefix=raw_key[:12],
        key_hash=hash_api_key(raw_key),
        scopes=scopes,
    )
    session.add(row)
    await session.flush()
    return ApiKey.model_validate(row), raw_key


async def get_api_key_by_hash(session: AsyncSession, key_hash: str) -> ApiKey | None:
    result = await session.execute(select(ApiKeyRow).where(ApiKeyRow.key_hash == key_hash))
    row = result.scalar_one_or_none()
    return ApiKey.model_validate(row) if row else None


async def list_api_keys_for_account(session: AsyncSession, account_id: uuid.UUID) -> list[ApiKey]:
    result = await session.execute(
        select(ApiKeyRow)
        .where(ApiKeyRow.account_id == account_id)
        .order_by(ApiKeyRow.created_at.desc())
    )
    return [ApiKey.model_validate(row) for row in result.scalars().all()]


async def revoke_api_key(session: AsyncSession, api_key_id: uuid.UUID) -> ApiKey | None:
    row = await session.get(ApiKeyRow, api_key_id)
    if row is None:
        return None
    row.revoked_at = datetime.now(UTC)
    await session.flush()
    return ApiKey.model_validate(row)


async def mark_api_key_used(session: AsyncSession, api_key_id: uuid.UUID, used_at: datetime) -> None:
    row = await session.get(ApiKeyRow, api_key_id)
    if row is not None:
        row.last_used_at = used_at
        await session.flush()


async def count_api_keys_for_account(session: AsyncSession, account_id: uuid.UUID) -> int:
    """Feeds `vigilo_billing.consume(..., Meter.API_KEYS, ...)` — a live
    `COUNT` of non-revoked keys, matching `count_monitors_for_account`'s
    precedent."""
    result = await session.execute(
        select(func.count())
        .select_from(ApiKeyRow)
        .where(ApiKeyRow.account_id == account_id, ApiKeyRow.revoked_at.is_(None))
    )
    return result.scalar_one()


async def get_branding_profile(session: AsyncSession, account_id: uuid.UUID) -> BrandingProfile | None:
    result = await session.execute(
        select(BrandingProfileRow).where(BrandingProfileRow.account_id == account_id)
    )
    row = result.scalar_one_or_none()
    return BrandingProfile.model_validate(row) if row else None


async def upsert_branding_profile(
    session: AsyncSession,
    account_id: uuid.UUID,
    logo_url: str | None = None,
    primary_color: str | None = None,
    footer_text: str | None = None,
    custom_domain: str | None = None,
) -> BrandingProfile:
    result = await session.execute(
        select(BrandingProfileRow).where(BrandingProfileRow.account_id == account_id)
    )
    row = result.scalar_one_or_none()

    if row is None:
        row = BrandingProfileRow(account_id=account_id)
        session.add(row)

    row.logo_url = logo_url
    row.primary_color = primary_color
    row.footer_text = footer_text
    row.custom_domain = custom_domain

    await session.flush()
    return BrandingProfile.model_validate(row)
