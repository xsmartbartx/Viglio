"""FastAPI dependencies: a per-request DB session, the Clerk-authenticated
account, and the ARQ enqueue pool.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated

from arq.connections import ArqRedis
from fastapi import Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from vigilo_api.auth import ClerkAuthError, verify_clerk_jwt
from vigilo_api.queue import get_arq_pool
from vigilo_identity.models import Account
from vigilo_identity.repository import get_account_by_clerk_id, get_or_create_account
from vigilo_persistence import session_scope


async def get_session() -> AsyncIterator[AsyncSession]:
    """One session per request, committed on a clean response and rolled
    back on any exception — including an `HTTPException` raised mid-handler.
    Endpoints that must persist a decision before an error response (e.g. a
    denied scan's audit event) commit explicitly before raising."""
    async with session_scope() as session:
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_session)]


def _bearer_token(request: Request) -> str:
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="missing bearer token")
    return header.removeprefix("Bearer ")


async def require_account(request: Request, session: SessionDep) -> Account:
    token = _bearer_token(request)
    try:
        claims = verify_clerk_jwt(token)
    except ClerkAuthError as exc:
        raise HTTPException(status_code=401, detail=exc.message) from exc

    account = await get_account_by_clerk_id(session, claims.user_id)
    if account is not None:
        return account

    if not claims.email:
        raise HTTPException(status_code=401, detail="session token has no email claim")
    return await get_or_create_account(session, email=claims.email, clerk_user_id=claims.user_id)


AccountDep = Annotated[Account, Depends(require_account)]


async def optional_account(request: Request, session: SessionDep) -> Account | None:
    """Missing `Authorization` header → anonymous view (`None`). A header
    that IS present but invalid/expired still raises `401` — never silently
    swallowed into an anonymous view, which would hide a real auth error
    from the caller."""
    if "Authorization" not in request.headers:
        return None
    return await require_account(request, session)


OptionalAccountDep = Annotated[Account | None, Depends(optional_account)]


async def get_queue() -> ArqRedis:
    return await get_arq_pool()


QueueDep = Annotated[ArqRedis, Depends(get_queue)]
