from __future__ import annotations

import uuid

import vigilo_api.routers.scans as scans_module
from vigilo_core.models import VerificationMethod
from vigilo_identity.repository import get_or_create_account
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
    already-verified target for this exact origin gets active tier through
    the actual submission path, not just in theory."""
    async with session_scope() as session:
        account = await get_or_create_account(session, email="verified-owner@example.com")
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
