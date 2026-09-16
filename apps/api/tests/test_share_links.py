from __future__ import annotations

import uuid

from vigilo_api.deps import require_account
from vigilo_api.main import app
from vigilo_core.models import Confidence, Finding, Score, Severity, Tier, Verdict
from vigilo_identity.repository import get_account_by_id, get_or_create_account, upsert_subscription
from vigilo_orchestrator.service import advance, create_scan_job, record_scan_result
from vigilo_persistence import session_scope
from vigilo_project.repository import create_target, get_or_create_default_project


async def _make_completed_scan(email: str = "owner@example.com"):
    async with session_scope() as session:
        account = await get_or_create_account(session, email=email)
        # Free plan doesn't include share links (Phase 7) — these tests are
        # about the share-link lifecycle, not plan gating, so seed a plan
        # that has them.
        await upsert_subscription(
            session,
            account_id=account.id,
            plan_id="builder",
            status="active",
            provider="paddle",
            provider_subscription_id=f"sub_{email}",
            current_period_end=None,
        )
        account = await get_account_by_id(session, account.id)
        project = await get_or_create_default_project(session, account.id)
        target = await create_target(session, project.id, "https://example.com")
        job = await create_scan_job(session, target.id, Tier.PASSIVE, email, "0.1")
        job = await advance(session, job.id, "authorized")
        job = await advance(session, job.id, "probing")
        job = await advance(session, job.id, "evaluating")
        job = await advance(session, job.id, "scoring")

        findings = [
            Finding(
                check_id="VG-HDR-001",
                verdict=Verdict.FAILED,
                severity=Severity.HIGH,
                confidence=Confidence.CONFIRMED,
                title="HSTS enforced",
                summary="No HSTS header present.",
                fingerprint="fp1",
            )
        ]
        score = Score(value=72.0, grade="C", registry_version="0.1")
        scan = await record_scan_result(session, job, findings, score, duration_ms=10)
        await advance(session, job.id, "reporting")
        await advance(session, job.id, "complete")
    return job, scan, account


async def test_create_share_link_requires_authentication(client):
    job, _scan, _account = await _make_completed_scan()
    response = await client.post(f"/v1/scans/{job.id}/share-links", json={})
    assert response.status_code == 401


async def test_create_and_resolve_share_link(client):
    job, _scan, account = await _make_completed_scan()
    app.dependency_overrides[require_account] = lambda: account

    create_response = await client.post(
        f"/v1/scans/{job.id}/share-links", json={"expires_in_days": 7}
    )
    assert create_response.status_code == 201
    body = create_response.json()
    assert body["expires_at"] is not None
    token = body["token"]

    resolve_response = await client.get(f"/v1/share/{token}")
    assert resolve_response.status_code == 200
    resolved = resolve_response.json()
    assert resolved["target_origin"] == "https://example.com"
    assert resolved.get("scan_job_id") is None
    assert resolved.get("is_owner") is None
    assert len(resolved["findings"]) == 1


async def test_resolve_an_unknown_token_returns_404(client):
    response = await client.get("/v1/share/not-a-real-token")
    assert response.status_code == 404


async def test_list_share_links_shows_created_links(client):
    job, _scan, account = await _make_completed_scan()
    app.dependency_overrides[require_account] = lambda: account

    await client.post(f"/v1/scans/{job.id}/share-links", json={})
    list_response = await client.get(f"/v1/scans/{job.id}/share-links")

    assert list_response.status_code == 200
    links = list_response.json()
    assert len(links) == 1
    assert "token_hash" not in links[0]
    assert "token" not in links[0]


async def test_revoke_share_link_denies_further_resolution(client):
    job, _scan, account = await _make_completed_scan()
    app.dependency_overrides[require_account] = lambda: account

    create_response = await client.post(f"/v1/scans/{job.id}/share-links", json={})
    body = create_response.json()

    revoke_response = await client.post(f"/v1/share-links/{body['share_link_id']}/revoke")
    assert revoke_response.status_code == 200
    assert revoke_response.json()["revoked_at"] is not None

    resolve_response = await client.get(f"/v1/share/{body['token']}")
    assert resolve_response.status_code == 410


async def test_someone_else_cannot_create_a_share_link_for_a_scan_they_do_not_own(client):
    job, _scan, _owner = await _make_completed_scan("owner@example.com")

    async with session_scope() as session:
        other = await get_or_create_account(session, email="other@example.com")
    app.dependency_overrides[require_account] = lambda: other

    response = await client.post(f"/v1/scans/{job.id}/share-links", json={})
    assert response.status_code == 404


async def test_create_share_link_is_denied_on_the_free_plan(client):
    """Free plan doesn't include share links (packages/billing/plans.py) —
    unlike `_make_completed_scan`'s other callers, this test deliberately
    leaves the account on its default (Free) plan."""
    async with session_scope() as session:
        account = await get_or_create_account(session, email="free-owner@example.com")
        project = await get_or_create_default_project(session, account.id)
        target = await create_target(session, project.id, "https://example.com")
        job = await create_scan_job(session, target.id, Tier.PASSIVE, account.email, "0.1")
        job = await advance(session, job.id, "authorized")
        job = await advance(session, job.id, "probing")
        job = await advance(session, job.id, "evaluating")
        job = await advance(session, job.id, "scoring")
        findings = [
            Finding(
                check_id="VG-HDR-001",
                verdict=Verdict.FAILED,
                severity=Severity.HIGH,
                confidence=Confidence.CONFIRMED,
                title="HSTS enforced",
                summary="No HSTS header present.",
                fingerprint="fp1",
            )
        ]
        score = Score(value=72.0, grade="C", registry_version="0.1")
        await record_scan_result(session, job, findings, score, duration_ms=10)
        await advance(session, job.id, "reporting")
        await advance(session, job.id, "complete")
    app.dependency_overrides[require_account] = lambda: account

    response = await client.post(f"/v1/scans/{job.id}/share-links", json={})

    assert response.status_code == 429
    assert response.json()["code"] == "QUOTA_EXCEEDED"


async def test_revoke_of_an_unknown_share_link_returns_404(client):
    async with session_scope() as session:
        account = await get_or_create_account(session, email="owner2@example.com")
    app.dependency_overrides[require_account] = lambda: account

    response = await client.post(f"/v1/share-links/{uuid.uuid4()}/revoke")
    assert response.status_code == 404
