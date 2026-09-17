"""Project/Target/OwnershipProof repository. Every function takes an
already-open `AsyncSession` — see `vigilo_identity.repository`'s module
docstring for why.
"""

from __future__ import annotations

import secrets
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from vigilo_core.models import Target, Tier, VerificationMethod
from vigilo_project.errors import OwnershipProofNotFound
from vigilo_project.models import OwnershipProof, Project
from vigilo_project.orm import OwnershipProofRow, ProjectRow, TargetRow

_PROOF_LIFETIME = timedelta(days=90)  # ADR-0003: proofs expire after 90 days


def _target_from_row(row: TargetRow) -> Target:
    return Target(
        id=row.id,
        project_id=row.project_id,
        origin=row.origin,
        verification_status=Tier(row.verification_status),
        verified_at=row.verified_at,
        verification_method=row.verification_method,
        opt_out_flag=row.opt_out_flag,
    )


async def get_or_create_default_project(session: AsyncSession, account_id: uuid.UUID) -> Project:
    """No project-management UI this phase — every account gets exactly one
    project, named "Default", created lazily on first use."""
    result = await session.execute(select(ProjectRow).where(ProjectRow.account_id == account_id))
    row = result.scalar_one_or_none()

    if row is None:
        row = ProjectRow(account_id=account_id, name="Default")
        session.add(row)
        await session.flush()

    return Project.model_validate(row)


async def get_project(session: AsyncSession, project_id: uuid.UUID) -> Project | None:
    """The other direction of `get_or_create_default_project()` — from a
    `project_id` (e.g. `Target.project_id`) back to its owning `Project`
    (and via `Project.account_id`, its account). Needed for Phase 9's
    branding lookup: a report is rendered from a `Target`, which only
    carries `project_id`, not `account_id` directly."""
    row = await session.get(ProjectRow, project_id)
    return Project.model_validate(row) if row else None


async def create_target(session: AsyncSession, project_id: uuid.UUID, origin: str) -> Target:
    result = await session.execute(
        select(TargetRow).where(TargetRow.project_id == project_id, TargetRow.origin == origin)
    )
    row = result.scalar_one_or_none()

    if row is None:
        row = TargetRow(project_id=project_id, origin=origin)
        session.add(row)
        await session.flush()

    return _target_from_row(row)


async def list_target_ids_for_project(
    session: AsyncSession, project_id: uuid.UUID
) -> list[uuid.UUID]:
    """Composes the id list `vigilo_orchestrator.service
    .count_scan_jobs_for_targets` needs — that module never imports
    `vigilo_project.orm` directly, per docs/modules.md §8."""
    result = await session.execute(
        select(TargetRow.id).where(TargetRow.project_id == project_id)
    )
    return list(result.scalars().all())


async def count_targets_for_project(session: AsyncSession, project_id: uuid.UUID) -> int:
    """Feeds `vigilo_billing.consume(..., Meter.TARGETS, ...)` — a live
    `COUNT`, not a stored counter, so there's nothing to decrement or drift
    out of sync (docs/build-roadmap.md's Phase 7 framing)."""
    result = await session.execute(
        select(func.count()).select_from(TargetRow).where(TargetRow.project_id == project_id)
    )
    return result.scalar_one()


async def get_target(session: AsyncSession, target_id: uuid.UUID) -> Target | None:
    row = await session.get(TargetRow, target_id)
    return _target_from_row(row) if row else None


async def get_target_by_origin(
    session: AsyncSession, project_id: uuid.UUID, origin: str
) -> Target | None:
    result = await session.execute(
        select(TargetRow).where(TargetRow.project_id == project_id, TargetRow.origin == origin)
    )
    row = result.scalar_one_or_none()
    return _target_from_row(row) if row else None


async def set_opt_out(session: AsyncSession, target_id: uuid.UUID, flag: bool) -> None:
    row = await session.get(TargetRow, target_id)
    if row is not None:
        row.opt_out_flag = flag
        await session.flush()


async def issue_ownership_proof(
    session: AsyncSession, target_id: uuid.UUID, method: VerificationMethod
) -> OwnershipProof:
    row = OwnershipProofRow(
        target_id=target_id, method=method.value, nonce=secrets.token_urlsafe(32)
    )
    session.add(row)
    await session.flush()
    return OwnershipProof.model_validate(row)


async def get_ownership_proof(session: AsyncSession, proof_id: uuid.UUID) -> OwnershipProof | None:
    row = await session.get(OwnershipProofRow, proof_id)
    return OwnershipProof.model_validate(row) if row else None


async def has_valid_ownership_proof(session: AsyncSession, target_id: uuid.UUID) -> bool:
    """The `ownership_proof_valid` input `resolve_authorization()` needs
    (ADR-0003: a lapsed proof downgrades future scans to passive rather than
    failing them, so this is a plain boolean, not an error)."""
    result = await session.execute(
        select(OwnershipProofRow).where(
            OwnershipProofRow.target_id == target_id,
            OwnershipProofRow.verified_at.is_not(None),
        )
    )
    rows = result.scalars().all()
    now = datetime.now(UTC)
    return any(row.expires_at is not None and row.expires_at > now for row in rows)


async def mark_proof_verified(session: AsyncSession, proof_id: uuid.UUID) -> OwnershipProof:
    """Immutability of a verified proof ("immutable once verified" per the
    domain model) is enforced here at the application layer only, by simply
    never being called twice for the same proof in normal operation — a
    lighter guarantee than `audit_events`' database-level trigger. Cascades
    the owning `Target` to `Tier.ACTIVE`."""
    proof_row = await session.get(OwnershipProofRow, proof_id)
    if proof_row is None:
        raise OwnershipProofNotFound("ownership proof not found", proof_id=str(proof_id))

    now = datetime.now(UTC)
    proof_row.verified_at = now
    proof_row.expires_at = now + _PROOF_LIFETIME

    target_row = await session.get(TargetRow, proof_row.target_id)
    if target_row is not None:
        target_row.verification_status = Tier.ACTIVE.value
        target_row.verified_at = now
        target_row.verification_method = proof_row.method

    await session.flush()
    return OwnershipProof.model_validate(proof_row)
