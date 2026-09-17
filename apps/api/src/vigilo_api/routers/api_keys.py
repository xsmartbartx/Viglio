"""`POST`/`GET /v1/me/api-keys`, `POST /v1/me/api-keys/{id}/revoke` —
session-authenticated management of the keys that unlock `/public/v1/*`
(`apps/api/src/vigilo_api/api_key_auth.py`). Creating a key here is the
only place its plaintext is ever visible; every other read is by hash.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException

from vigilo_api.api_key_auth import ALL_SCOPES
from vigilo_api.deps import AccountDep, SessionDep
from vigilo_api.schemas import ApiKeyCreate, ApiKeyCreateResponse, ApiKeyResponse
from vigilo_billing import Meter, QuotaExceeded, consume, entitlements
from vigilo_identity.repository import (
    count_api_keys_for_account,
    create_api_key,
    list_api_keys_for_account,
    revoke_api_key,
)

router = APIRouter(prefix="/v1/me/api-keys", tags=["api-keys"])


def _to_response(api_key) -> ApiKeyResponse:
    return ApiKeyResponse(
        api_key_id=api_key.id,
        name=api_key.name,
        prefix=api_key.prefix,
        scopes=api_key.scopes,
        last_used_at=api_key.last_used_at,
        revoked_at=api_key.revoked_at,
        created_at=api_key.created_at,
    )


@router.post("", status_code=201, response_model=ApiKeyCreateResponse)
async def create_account_api_key(
    body: ApiKeyCreate, account: AccountDep, session: SessionDep
) -> ApiKeyCreateResponse:
    invalid_scopes = set(body.scopes) - ALL_SCOPES
    if invalid_scopes:
        raise HTTPException(status_code=422, detail=f"unknown scope(s): {sorted(invalid_scopes)}")

    plan = entitlements(account.plan_id)
    current_count = await count_api_keys_for_account(session, account.id)
    decision = consume(current_count, 1, Meter.API_KEYS, plan)
    if not decision.allowed:
        raise QuotaExceeded(
            "API key limit reached for plan", limit=decision.limit, current=decision.current
        )

    api_key, raw_key = await create_api_key(session, account.id, body.name, body.scopes)
    return ApiKeyCreateResponse(
        api_key_id=api_key.id,
        name=api_key.name,
        prefix=api_key.prefix,
        scopes=api_key.scopes,
        api_key=raw_key,
    )


@router.get("", response_model=list[ApiKeyResponse])
async def list_account_api_keys(account: AccountDep, session: SessionDep) -> list[ApiKeyResponse]:
    keys = await list_api_keys_for_account(session, account.id)
    return [_to_response(key) for key in keys]


@router.post("/{api_key_id}/revoke", response_model=ApiKeyResponse)
async def revoke_account_api_key(
    api_key_id: uuid.UUID, account: AccountDep, session: SessionDep
) -> ApiKeyResponse:
    # Ownership is checked by re-listing rather than trusting the id alone
    # — a plain 404 on mismatch (not 403), matching targets.py's precedent
    # of never letting ownership be probed by status code.
    owned_ids = {key.id for key in await list_api_keys_for_account(session, account.id)}
    if api_key_id not in owned_ids:
        raise HTTPException(status_code=404, detail="API key not found")

    revoked = await revoke_api_key(session, api_key_id)
    if revoked is None:
        raise HTTPException(status_code=404, detail="API key not found")
    return _to_response(revoked)
