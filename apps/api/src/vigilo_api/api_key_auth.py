"""API-key verification for the public REST API (`/public/v1/*`,
Phase 9) — a parallel, distinct auth scheme from `auth.py`'s Clerk JWT
verification, per the vision doc's "key-authenticated surface distinct
from the session-authenticated one." Mirrors `auth.py`'s shape: a small,
pure verification function plus the FastAPI dependency that calls it.

Unlike Clerk verification, there is no external JWKS call — a key is
"verified" by hashing the presented plaintext and looking up the hash, so
this needs a session, not a signing-key resolver.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends, HTTPException, Request

from vigilo_api.deps import SessionDep
from vigilo_billing import entitlements
from vigilo_identity.models import Account
from vigilo_identity.repository import (
    get_account_by_id,
    get_api_key_by_hash,
    hash_api_key,
    mark_api_key_used,
)
from vigilo_security.rate_limit import check_rate, get_redis_client

ALL_SCOPES = frozenset(
    {
        "scan:run",
        "scan:read",
        "project:read",
        "report:read",
        "monitor:read",
        "monitor:write",
    }
)


def _bearer_token(request: Request) -> str:
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="missing bearer token")
    return header.removeprefix("Bearer ")


async def require_api_key(request: Request, session: SessionDep) -> tuple[Account, frozenset[str]]:
    raw_key = _bearer_token(request)
    api_key = await get_api_key_by_hash(session, hash_api_key(raw_key))

    if api_key is None or api_key.revoked_at is not None:
        raise HTTPException(status_code=401, detail="invalid or revoked API key")

    account = await get_account_by_id(session, api_key.account_id)
    if account is None:
        raise HTTPException(status_code=401, detail="invalid or revoked API key")

    await mark_api_key_used(session, api_key.id, datetime.now(UTC))
    await session.commit()  # the usage stamp must survive even if the handler later fails

    return account, frozenset(api_key.scopes)


ApiKeyAuthDep = Annotated[tuple[Account, frozenset[str]], Depends(require_api_key)]


def require_scope(scope: str) -> Depends:
    """A dependency factory used in the *annotation*, not as a default
    value — `account: Annotated[Account, require_scope("scan:run")]` in
    each public-API route — matching this codebase's existing
    `Annotated[X, Depends(...)]` convention (`deps.py`'s `AccountDep`
    etc.) rather than FastAPI's older `= Depends(...)` default-argument
    style, which ruff's B008 rightly flags as fragile in general (even
    though FastAPI special-cases it) since Python only evaluates a
    default expression once at function-definition time.

    Also enforces the plan's per-minute rate limit (vision §12: "Rate
    limits per plan; 429 with Retry-After") — keyed by *account*, not by
    the individual API key: "per plan" reads as one shared budget for the
    account, not a separate budget per key it happens to have issued."""

    async def _check(auth: ApiKeyAuthDep) -> Account:
        account, scopes = auth
        if scope not in scopes:
            raise HTTPException(
                status_code=403, detail=f"API key is missing the required scope: {scope}"
            )

        limit = entitlements(account.plan_id).api_rate_limit_per_minute
        decision = await check_rate(get_redis_client(), f"ratelimit:{account.id}", limit)
        if not decision.allowed:
            raise HTTPException(
                status_code=429,
                detail="rate limit exceeded",
                headers={"Retry-After": str(decision.retry_after_seconds)},
            )

        return account

    return Depends(_check)
