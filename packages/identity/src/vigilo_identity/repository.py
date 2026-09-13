"""Account repository. Every function takes an already-open `AsyncSession`
rather than opening its own — the caller (an API handler or ARQ job body,
via `vigilo_persistence.session_scope`) controls the transaction boundary,
matching the pattern `vigilo_security.audit.audit()` uses for the same reason
(ADR-0003: a decision and everything it depends on commit together).
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from vigilo_identity.models import Account
from vigilo_identity.orm import AccountRow


async def get_account_by_id(session: AsyncSession, account_id: object) -> Account | None:
    row = await session.get(AccountRow, account_id)
    return Account.model_validate(row) if row else None


async def get_account_by_clerk_id(session: AsyncSession, clerk_user_id: str) -> Account | None:
    stmt = select(AccountRow).where(AccountRow.clerk_user_id == clerk_user_id)
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
