"""`POST /v1/targets`, `GET /v1/targets/{id}`, and the ownership-verification
pair — exit criterion (b). The verification-check endpoint always enqueues
`verify_ownership_job`, never runs a verification method inline: "the
control plane never makes an outbound request to a target, ever"
(docs/architecture.md §3), a rule the ADR-0003 Phase 3 addendum extends to
every verification method, not only the ones that fetch the target.
"""

from __future__ import annotations

import uuid

from arq.connections import ArqRedis
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from vigilo_core.config import config
from vigilo_core.models import Target, VerificationMethod
from vigilo_core.validation import ValidationError, validate_target_url
from vigilo_identity.models import Account
from vigilo_project.repository import (
    create_target,
    get_or_create_default_project,
    get_ownership_proof,
    get_target,
    issue_ownership_proof,
)

from vigilo_api.deps import get_queue, get_session, require_account
from vigilo_api.schemas import (
    TargetCreate,
    TargetResponse,
    VerificationCheckResponse,
    VerificationInitiate,
    VerificationInitiateResponse,
)

router = APIRouter(prefix="/v1/targets", tags=["targets"])


def _to_response(target: Target) -> TargetResponse:
    return TargetResponse(
        target_id=target.id,
        origin=target.origin,
        verification_status=target.verification_status,
        verified_at=target.verified_at,
        verification_method=target.verification_method,
    )


async def _owned_target_or_404(
    session: AsyncSession, account: Account, target_id: uuid.UUID
) -> Target:
    target = await get_target(session, target_id)
    project = await get_or_create_default_project(session, account.id)
    if target is None or target.project_id != project.id:
        raise HTTPException(status_code=404, detail="target not found")
    return target


@router.post("", status_code=201, response_model=TargetResponse)
async def create_target_endpoint(
    body: TargetCreate,
    account: Account = Depends(require_account),
    session: AsyncSession = Depends(get_session),
) -> TargetResponse:
    try:
        origin = validate_target_url(body.origin)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.message) from exc

    project = await get_or_create_default_project(session, account.id)
    target = await create_target(session, project.id, origin)
    return _to_response(target)


@router.get("/{target_id}", response_model=TargetResponse)
async def get_target_endpoint(
    target_id: uuid.UUID,
    account: Account = Depends(require_account),
    session: AsyncSession = Depends(get_session),
) -> TargetResponse:
    target = await _owned_target_or_404(session, account, target_id)
    return _to_response(target)


@router.post(
    "/{target_id}/verification", status_code=201, response_model=VerificationInitiateResponse
)
async def initiate_verification(
    target_id: uuid.UUID,
    body: VerificationInitiate,
    account: Account = Depends(require_account),
    session: AsyncSession = Depends(get_session),
) -> VerificationInitiateResponse:
    target = await _owned_target_or_404(session, account, target_id)
    proof = await issue_ownership_proof(session, target.id, body.method)

    namespaces = config().brand.namespaces
    dns_key = namespaces.get("dnsVerificationKey", "vigilo-site-verification")
    wellknown_path = namespaces.get("wellKnownPath", "/.well-known/vigilo-verification.txt")

    instructions = {
        VerificationMethod.DNS_TXT: f"Add a DNS TXT record: {dns_key}={proof.nonce}",
        VerificationMethod.WELLKNOWN_FILE: (
            f"Serve a file at {wellknown_path} whose content is exactly: {proof.nonce}"
        ),
        VerificationMethod.META_TAG: (
            f'Add <meta name="{dns_key}" content="{proof.nonce}"> to your homepage <head>.'
        ),
        VerificationMethod.EMAIL: "Email verification is not yet available.",
    }[body.method]

    return VerificationInitiateResponse(
        proof_id=proof.id, method=body.method, nonce=proof.nonce, instructions=instructions
    )


@router.post(
    "/{target_id}/verification/{proof_id}/check",
    status_code=202,
    response_model=VerificationCheckResponse,
)
async def check_verification(
    target_id: uuid.UUID,
    proof_id: uuid.UUID,
    account: Account = Depends(require_account),
    session: AsyncSession = Depends(get_session),
    queue: ArqRedis = Depends(get_queue),
) -> VerificationCheckResponse:
    await _owned_target_or_404(session, account, target_id)
    proof = await get_ownership_proof(session, proof_id)
    if proof is None or proof.target_id != target_id:
        raise HTTPException(status_code=404, detail="ownership proof not found")

    await queue.enqueue_job("verify_ownership_job", str(proof_id))
    return VerificationCheckResponse(proof_id=proof_id, status="checking")
