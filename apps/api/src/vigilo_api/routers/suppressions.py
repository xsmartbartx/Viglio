"""`POST /v1/targets/{id}/findings/suppress`, `GET /v1/targets/{id}/suppressions`,
`POST /v1/targets/{id}/suppressions/{id}/revoke` — the "known, accept it"
workflow, closing docs/prooflight-vision-and-architecture.md §6.2's
never-built acknowledged/muted lifecycle states as a target-scoped
suppression list rather than a full `Verdict` retrofit. Session-authenticated
only (not under `/public/v1/*`) — this is account configuration, matching
where API-key and branding management already live, not scan execution.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException

from vigilo_api.deps import AccountDep, SessionDep
from vigilo_api.routers.targets import _owned_target_or_404
from vigilo_api.schemas import SuppressionCreate, SuppressionResponse
from vigilo_project.models import Suppression
from vigilo_project.repository import (
    create_suppression,
    get_suppression,
    list_suppressions_for_target,
    revoke_suppression,
)
from vigilo_security.audit import AuditEvent, audit

router = APIRouter(tags=["suppressions"])


def _to_response(suppression: Suppression) -> SuppressionResponse:
    return SuppressionResponse(
        suppression_id=suppression.id,
        target_id=suppression.target_id,
        fingerprint=suppression.fingerprint,
        check_id=suppression.check_id,
        reason=suppression.reason,
        expires_at=suppression.expires_at,
        created_by_account_id=suppression.created_by_account_id,
        created_at=suppression.created_at,
    )


@router.post(
    "/v1/targets/{target_id}/findings/suppress",
    status_code=201,
    response_model=SuppressionResponse,
)
async def suppress_finding(
    target_id: uuid.UUID,
    body: SuppressionCreate,
    account: AccountDep,
    session: SessionDep,
) -> SuppressionResponse:
    target = await _owned_target_or_404(session, account, target_id)
    suppression = await create_suppression(
        session,
        target_id=target.id,
        fingerprint=body.fingerprint,
        check_id=body.check_id,
        reason=body.reason,
        created_by_account_id=account.id,
        expires_at=body.expires_at,
    )
    await audit(
        session,
        AuditEvent(
            actor=str(account.id),
            action="finding_suppressed",
            subject=suppression.fingerprint,
            account_id=account.id,
            metadata={"target_id": str(target.id), "check_id": suppression.check_id},
        ),
    )
    return _to_response(suppression)


@router.get("/v1/targets/{target_id}/suppressions", response_model=list[SuppressionResponse])
async def list_target_suppressions(
    target_id: uuid.UUID, account: AccountDep, session: SessionDep
) -> list[SuppressionResponse]:
    target = await _owned_target_or_404(session, account, target_id)
    suppressions = await list_suppressions_for_target(session, target.id)
    return [_to_response(suppression) for suppression in suppressions]


@router.post(
    "/v1/targets/{target_id}/suppressions/{suppression_id}/revoke",
    response_model=SuppressionResponse,
)
async def revoke_target_suppression(
    target_id: uuid.UUID,
    suppression_id: uuid.UUID,
    account: AccountDep,
    session: SessionDep,
) -> SuppressionResponse:
    await _owned_target_or_404(session, account, target_id)

    # Ownership of the suppression itself is checked via its target_id match
    # — a plain 404 on mismatch (not 403), matching api_keys.py's
    # never-let-ownership-be-probed-by-status-code precedent.
    existing = await get_suppression(session, suppression_id)
    if existing is None or existing.target_id != target_id:
        raise HTTPException(status_code=404, detail="suppression not found")

    revoked = await revoke_suppression(session, suppression_id)
    if revoked is None:
        raise HTTPException(status_code=404, detail="suppression not found")

    await audit(
        session,
        AuditEvent(
            actor=str(account.id),
            action="finding_unsuppressed",
            subject=revoked.fingerprint,
            account_id=account.id,
            metadata={"target_id": str(target_id), "check_id": revoked.check_id},
        ),
    )
    return _to_response(revoked)
