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
from datetime import datetime

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
