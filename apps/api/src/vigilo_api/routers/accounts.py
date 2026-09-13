"""`GET /v1/me` — the first call after a Clerk sign-in. `require_account`
auto-provisions the `Account` (and links it to an earlier anonymous account
created by a free scan under the same email, if one exists).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from vigilo_api.deps import require_account
from vigilo_api.schemas import AccountResponse
from vigilo_identity.models import Account

router = APIRouter(prefix="/v1", tags=["accounts"])


@router.get("/me", response_model=AccountResponse)
async def get_me(account: Account = Depends(require_account)) -> AccountResponse:
    return AccountResponse(
        account_id=account.id,
        email=account.email,
        status=account.status,
        created_at=account.created_at,
    )
