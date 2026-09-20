from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from vigilo_core.models import Tier, VerificationMethod
from vigilo_identity.repository import get_or_create_account
from vigilo_project.orm import OwnershipProofRow
from vigilo_project.repository import (
    create_suppression,
    create_target,
    get_or_create_default_project,
    get_suppressed_fingerprints_for_target,
    get_target,
    get_target_by_origin,
    has_valid_ownership_proof,
    issue_ownership_proof,
    list_suppressions_for_target,
    list_targets_for_project,
    mark_proof_verified,
    revoke_suppression,
    set_opt_out,
)


async def _account_id(session: AsyncSession, email: str = "owner@example.com"):
    account = await get_or_create_account(session, email=email)
    return account.id


async def test_get_or_create_default_project_is_idempotent(db_session: AsyncSession) -> None:
    account_id = await _account_id(db_session)

    first = await get_or_create_default_project(db_session, account_id)
    second = await get_or_create_default_project(db_session, account_id)

    assert first.id == second.id
    assert first.name == "Default"


async def test_create_target_is_idempotent_per_project_and_origin(db_session: AsyncSession) -> None:
    account_id = await _account_id(db_session)
    project = await get_or_create_default_project(db_session, account_id)

    first = await create_target(db_session, project.id, "https://example.com")
    second = await create_target(db_session, project.id, "https://example.com")

    assert first.id == second.id
    assert first.verification_status == Tier.PASSIVE
    assert first.opt_out_flag is False


async def test_list_targets_for_project_returns_only_that_projects_targets(
    db_session: AsyncSession,
) -> None:
    project = await get_or_create_default_project(db_session, await _account_id(db_session))
    other_project = await get_or_create_default_project(
        db_session, await _account_id(db_session, email="other@example.com")
    )
    first = await create_target(db_session, project.id, "https://a.example.com")
    second = await create_target(db_session, project.id, "https://b.example.com")
    await create_target(db_session, other_project.id, "https://c.example.com")

    targets = await list_targets_for_project(db_session, project.id)

    assert {target.id for target in targets} == {first.id, second.id}


async def test_get_target_and_get_target_by_origin_agree(db_session: AsyncSession) -> None:
    account_id = await _account_id(db_session)
    project = await get_or_create_default_project(db_session, account_id)
    created = await create_target(db_session, project.id, "https://example.com")

    by_id = await get_target(db_session, created.id)
    by_origin = await get_target_by_origin(db_session, project.id, "https://example.com")

    assert by_id is not None and by_origin is not None
    assert by_id.id == by_origin.id == created.id


async def test_set_opt_out_flips_the_flag(db_session: AsyncSession) -> None:
    account_id = await _account_id(db_session)
    project = await get_or_create_default_project(db_session, account_id)
    target = await create_target(db_session, project.id, "https://example.com")

    await set_opt_out(db_session, target.id, True)

    reloaded = await get_target(db_session, target.id)
    assert reloaded is not None
    assert reloaded.opt_out_flag is True


async def test_issuing_a_proof_generates_a_random_nonce(db_session: AsyncSession) -> None:
    account_id = await _account_id(db_session)
    project = await get_or_create_default_project(db_session, account_id)
    target = await create_target(db_session, project.id, "https://example.com")

    proof_a = await issue_ownership_proof(db_session, target.id, VerificationMethod.DNS_TXT)
    proof_b = await issue_ownership_proof(db_session, target.id, VerificationMethod.DNS_TXT)

    assert proof_a.nonce != proof_b.nonce
    assert proof_a.verified_at is None


async def test_a_target_with_no_proofs_has_no_valid_proof(db_session: AsyncSession) -> None:
    account_id = await _account_id(db_session)
    project = await get_or_create_default_project(db_session, account_id)
    target = await create_target(db_session, project.id, "https://example.com")

    assert await has_valid_ownership_proof(db_session, target.id) is False


async def test_marking_a_proof_verified_upgrades_the_target_to_active(
    db_session: AsyncSession,
) -> None:
    account_id = await _account_id(db_session)
    project = await get_or_create_default_project(db_session, account_id)
    target = await create_target(db_session, project.id, "https://example.com")
    proof = await issue_ownership_proof(db_session, target.id, VerificationMethod.META_TAG)

    verified = await mark_proof_verified(db_session, proof.id)
    reloaded = await get_target(db_session, target.id)

    assert verified.verified_at is not None
    assert verified.expires_at is not None
    assert reloaded is not None
    assert reloaded.verification_status == Tier.ACTIVE
    assert reloaded.verification_method == VerificationMethod.META_TAG.value
    assert await has_valid_ownership_proof(db_session, target.id) is True


async def test_an_expired_proof_is_not_counted_as_valid(db_session: AsyncSession) -> None:
    account_id = await _account_id(db_session)
    project = await get_or_create_default_project(db_session, account_id)
    target = await create_target(db_session, project.id, "https://example.com")
    proof = await issue_ownership_proof(db_session, target.id, VerificationMethod.DNS_TXT)
    await mark_proof_verified(db_session, proof.id)

    # Simulate the 90-day lifetime having already elapsed.
    row = await db_session.get(OwnershipProofRow, proof.id)
    assert row is not None
    row.expires_at = datetime.now(UTC) - timedelta(days=1)
    await db_session.flush()

    assert await has_valid_ownership_proof(db_session, target.id) is False


async def test_create_suppression_and_it_shows_up_as_suppressed(db_session: AsyncSession) -> None:
    account_id = await _account_id(db_session)
    project = await get_or_create_default_project(db_session, account_id)
    target = await create_target(db_session, project.id, "https://example.com")

    await create_suppression(
        db_session,
        target.id,
        fingerprint="fp-abc",
        check_id="VG-HDR-001",
        reason="Accepted — behind a CDN that already sets this.",
        created_by_account_id=account_id,
    )

    suppressed = await get_suppressed_fingerprints_for_target(
        db_session, target.id, datetime.now(UTC)
    )
    assert suppressed == frozenset({"fp-abc"})


async def test_create_suppression_upserts_by_target_and_fingerprint(
    db_session: AsyncSession,
) -> None:
    account_id = await _account_id(db_session)
    project = await get_or_create_default_project(db_session, account_id)
    target = await create_target(db_session, project.id, "https://example.com")

    first = await create_suppression(
        db_session, target.id, "fp-abc", "VG-HDR-001", "first reason", account_id
    )
    second = await create_suppression(
        db_session, target.id, "fp-abc", "VG-HDR-001", "updated reason", account_id
    )

    assert second.id == first.id
    assert second.reason == "updated reason"

    suppressions = await list_suppressions_for_target(db_session, target.id)
    assert len(suppressions) == 1


async def test_expired_suppressions_are_excluded(db_session: AsyncSession) -> None:
    account_id = await _account_id(db_session)
    project = await get_or_create_default_project(db_session, account_id)
    target = await create_target(db_session, project.id, "https://example.com")

    await create_suppression(
        db_session,
        target.id,
        "fp-expired",
        "VG-HDR-001",
        "temporary",
        account_id,
        expires_at=datetime.now(UTC) - timedelta(days=1),
    )
    await create_suppression(
        db_session,
        target.id,
        "fp-permanent",
        "VG-HDR-002",
        "permanent",
        account_id,
    )

    suppressed = await get_suppressed_fingerprints_for_target(
        db_session, target.id, datetime.now(UTC)
    )
    assert suppressed == frozenset({"fp-permanent"})


async def test_revoke_suppression_removes_it(db_session: AsyncSession) -> None:
    account_id = await _account_id(db_session)
    project = await get_or_create_default_project(db_session, account_id)
    target = await create_target(db_session, project.id, "https://example.com")
    suppression = await create_suppression(
        db_session, target.id, "fp-abc", "VG-HDR-001", "reason", account_id
    )

    revoked = await revoke_suppression(db_session, suppression.id)

    assert revoked is not None
    assert revoked.id == suppression.id
    suppressed = await get_suppressed_fingerprints_for_target(
        db_session, target.id, datetime.now(UTC)
    )
    assert suppressed == frozenset()


async def test_revoke_suppression_returns_none_for_an_unknown_id(db_session: AsyncSession) -> None:
    assert await revoke_suppression(db_session, uuid.uuid4()) is None
