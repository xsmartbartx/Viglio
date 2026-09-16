from __future__ import annotations

import uuid

import vigilo_api.routers.scans as scans_module
from vigilo_core.models import Tier, VerificationMethod
from vigilo_identity.repository import get_or_create_account, upsert_subscription
from vigilo_orchestrator.service import create_scan_job
from vigilo_persistence import session_scope
from vigilo_project.repository import (
    create_target,
    get_or_create_default_project,
    issue_ownership_proof,
    mark_proof_verified,
)


async def test_submit_scan_returns_202_with_the_authorized_status(client):
    response = await client.post(
        "/v1/scans", json={"target_url": "https://example.com", "email": "owner@example.com"}
    )

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "authorized"
    assert body["granted_tier"] == "passive"
    assert "scan_job_id" in body


async def test_submit_scan_rejects_a_malformed_url(client):
    response = await client.post(
        "/v1/scans", json={"target_url": "not-a-url", "email": "owner@example.com"}
    )
    assert response.status_code == 422


async def test_submit_scan_rejects_an_invalid_email(client):
    response = await client.post(
        "/v1/scans", json={"target_url": "https://example.com", "email": "not-an-email"}
    )
    assert response.status_code == 422


async def test_submit_scan_denies_a_denylisted_target(client, monkeypatch):
    monkeypatch.setattr(scans_module, "_DENYLIST", frozenset({"https://denylisted.test"}))

    response = await client.post(
        "/v1/scans", json={"target_url": "https://denylisted.test", "email": "owner@example.com"}
    )
    assert response.status_code == 403


async def test_get_scan_status_returns_404_for_an_unknown_job(client):
    response = await client.get(f"/v1/scans/{uuid.uuid4()}")
    assert response.status_code == 404


async def test_submit_scan_requesting_active_tier_stays_passive_for_a_new_target(client):
    """A brand-new submitter has no prior verification state — requesting
    active tier is a downgrade, not a rejection, per ADR-0003."""
    response = await client.post(
        "/v1/scans",
        json={
            "target_url": "https://example.com",
            "email": "first-timer@example.com",
            "requested_tier": "active",
        },
    )

    assert response.status_code == 202
    assert response.json()["granted_tier"] == "passive"


async def test_submit_scan_grants_active_tier_for_a_returning_verified_target(client):
    """The tier-stub fix (Phase 6): a returning submitter with a real,
    already-verified target for this exact origin, on a plan that includes
    active tier (Phase 7 — Free does not), gets active tier through the
    actual submission path, not just in theory."""
    async with session_scope() as session:
        account = await get_or_create_account(session, email="verified-owner@example.com")
        await upsert_subscription(
            session,
            account_id=account.id,
            plan_id="builder",
            status="active",
            provider="paddle",
            provider_subscription_id="sub_verified_owner",
            current_period_end=None,
        )
        project = await get_or_create_default_project(session, account.id)
        target = await create_target(session, project.id, "https://example.com")
        proof = await issue_ownership_proof(session, target.id, VerificationMethod.DNS_TXT)
        await mark_proof_verified(session, proof.id)

    response = await client.post(
        "/v1/scans",
        json={
            "target_url": "https://example.com",
            "email": "verified-owner@example.com",
            "requested_tier": "active",
        },
    )

    assert response.status_code == 202
    assert response.json()["granted_tier"] == "active"


async def test_submit_scan_with_valid_proof_but_free_plan_stays_passive(client):
    """Phase 7's plan gate: a verified ownership proof alone is no longer
    enough for active tier — the account's plan (defaulting to Free, which
    excludes active tier) must permit it too. The concrete, testable
    analogue of the roadmap's "a plan change correctly and immediately
    restricts access" exit criterion."""
    async with session_scope() as session:
        account = await get_or_create_account(session, email="free-but-verified@example.com")
        project = await get_or_create_default_project(session, account.id)
        target = await create_target(session, project.id, "https://example.com")
        proof = await issue_ownership_proof(session, target.id, VerificationMethod.DNS_TXT)
        await mark_proof_verified(session, proof.id)

    response = await client.post(
        "/v1/scans",
        json={
            "target_url": "https://example.com",
            "email": "free-but-verified@example.com",
            "requested_tier": "active",
        },
    )

    assert response.status_code == 202
    assert response.json()["granted_tier"] == "passive"


async def test_submit_scan_for_a_new_origin_beyond_the_free_plan_target_limit_is_denied(client):
    """The bypass fix: `submit_scan` used to auto-create a `Target` for any
    new origin a returning account scanned, with no quota check at all.
    Free plan's targets_limit is 1 — a returning account with one existing
    target, scanning a second, brand-new origin, must be denied exactly
    like `POST /v1/targets` would deny it."""
    async with session_scope() as session:
        account = await get_or_create_account(session, email="repeat-scanner@example.com")
        project = await get_or_create_default_project(session, account.id)
        await create_target(session, project.id, "https://first.example.com")

    response = await client.post(
        "/v1/scans",
        json={"target_url": "https://second.example.com", "email": "repeat-scanner@example.com"},
    )

    assert response.status_code == 429
    assert response.json()["code"] == "QUOTA_EXCEEDED"


async def test_submit_scan_beyond_the_free_plan_monthly_scan_limit_is_denied(client):
    """Free plan's scans_per_month_limit is 3 (packages/billing/plans.py) —
    a 4th scan within the rolling 30-day window, even of an already-known
    target, is denied."""
    async with session_scope() as session:
        account = await get_or_create_account(session, email="frequent-scanner@example.com")
        project = await get_or_create_default_project(session, account.id)
        target = await create_target(session, project.id, "https://example.com")
        for _ in range(3):
            await create_scan_job(session, target.id, Tier.PASSIVE, account.email, "0.1")

    response = await client.post(
        "/v1/scans",
        json={"target_url": "https://example.com", "email": "frequent-scanner@example.com"},
    )

    assert response.status_code == 429
    assert response.json()["code"] == "QUOTA_EXCEEDED"


async def test_get_scan_status_reflects_the_authorized_job(client):
    submit_response = await client.post(
        "/v1/scans", json={"target_url": "https://example.com", "email": "owner@example.com"}
    )
    job_id = submit_response.json()["scan_job_id"]

    response = await client.get(f"/v1/scans/{job_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "authorized"
    assert body["target_origin"] == "https://example.com"
    assert body["score"] is None
