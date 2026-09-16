from __future__ import annotations

import uuid

from vigilo_core.models import Confidence, Finding, Score, Severity, Tier, Verdict
from vigilo_identity.repository import get_or_create_account
from vigilo_orchestrator.service import advance, create_scan_job, record_scan_result
from vigilo_persistence import session_scope
from vigilo_project.repository import create_target, get_or_create_default_project


async def _scanned_target():
    async with session_scope() as session:
        account = await get_or_create_account(session, email="badge-owner@example.com")
        project = await get_or_create_default_project(session, account.id)
        target = await create_target(session, project.id, "https://example.com")
        job = await create_scan_job(session, target.id, Tier.PASSIVE, account.email, "0.1")
        job = await advance(session, job.id, "authorized")
        job = await advance(session, job.id, "probing")
        job = await advance(session, job.id, "evaluating")
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
        job = await advance(session, job.id, "scoring")
        score = Score(value=83.0, grade="B", registry_version="0.1")
        await record_scan_result(session, job, findings, score, duration_ms=10)
        await advance(session, job.id, "reporting")
        await advance(session, job.id, "complete")
    return target.id


async def test_badge_returns_an_svg_for_a_scanned_target(client):
    target_id = await _scanned_target()

    response = await client.get(f"/badge/{target_id}.svg")

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/svg+xml"
    assert response.headers["cache-control"] == "public, max-age=3600"
    assert response.text.startswith("<svg")
    assert "B" in response.text


async def test_badge_returns_404_for_a_target_with_no_scan_yet(client):
    async with session_scope() as session:
        account = await get_or_create_account(session, email="no-scan@example.com")
        project = await get_or_create_default_project(session, account.id)
        target = await create_target(session, project.id, "https://never-scanned.example.com")

    response = await client.get(f"/badge/{target.id}.svg")

    assert response.status_code == 404


async def test_badge_returns_404_for_an_unknown_target(client):
    response = await client.get(f"/badge/{uuid.uuid4()}.svg")
    assert response.status_code == 404


async def test_badge_is_public_and_requires_no_authentication(client):
    target_id = await _scanned_target()

    response = await client.get(f"/badge/{target_id}.svg")

    assert response.status_code == 200
