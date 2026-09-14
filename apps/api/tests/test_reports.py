from __future__ import annotations

import uuid

from vigilo_api.deps import optional_account
from vigilo_api.main import app
from vigilo_core.models import Confidence, Finding, Score, Severity, Tier, Verdict
from vigilo_identity.repository import get_or_create_account
from vigilo_integrations.storage import put_report_pdf
from vigilo_orchestrator.reports import get_or_create_pdf_report, mark_report_complete
from vigilo_orchestrator.service import advance, create_scan_job, record_scan_result
from vigilo_persistence import session_scope
from vigilo_project.repository import create_target, get_or_create_default_project


async def _make_completed_scan(email: str = "owner@example.com"):
    async with session_scope() as session:
        account = await get_or_create_account(session, email=email)
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


async def test_get_scan_report_returns_404_for_an_unknown_job(client):
    response = await client.get(f"/v1/scans/{uuid.uuid4()}/report")
    assert response.status_code == 404


async def test_get_scan_report_returns_409_when_scan_not_yet_scored(client):
    async with session_scope() as session:
        account = await get_or_create_account(session, email="x@example.com")
        project = await get_or_create_default_project(session, account.id)
        target = await create_target(session, project.id, "https://example.com")
        job = await create_scan_job(session, target.id, Tier.PASSIVE, "x@example.com", "0.1")

    response = await client.get(f"/v1/scans/{job.id}/report")
    assert response.status_code == 409


async def test_get_scan_report_returns_full_findings_for_a_completed_scan(client):
    job, _scan, _account = await _make_completed_scan()

    response = await client.get(f"/v1/scans/{job.id}/report")

    assert response.status_code == 200
    body = response.json()
    assert body["target_origin"] == "https://example.com"
    assert body["grade"] == "C"
    assert body["is_owner"] is False
    assert len(body["findings"]) == 1
    finding = body["findings"][0]
    assert finding["check_id"] == "VG-HDR-001"
    assert finding["category"] == "HDR"
    assert finding["remediation"]
    assert finding["evidence"] is None


async def test_get_scan_report_reports_is_owner_true_for_the_authenticated_owner(client):
    job, _scan, account = await _make_completed_scan()
    app.dependency_overrides[optional_account] = lambda: account

    response = await client.get(f"/v1/scans/{job.id}/report")

    assert response.status_code == 200
    assert response.json()["is_owner"] is True


async def test_request_report_pdf_is_idempotent(client):
    job, _scan, _account = await _make_completed_scan()

    first = await client.post(f"/v1/scans/{job.id}/report/pdf")
    second = await client.post(f"/v1/scans/{job.id}/report/pdf")

    assert first.status_code == 202
    assert second.status_code == 202
    assert first.json()["report_id"] == second.json()["report_id"]
    assert first.json()["status"] == "pending"


async def test_get_report_pdf_status_before_render_has_no_download_url(client):
    job, _scan, _account = await _make_completed_scan()
    await client.post(f"/v1/scans/{job.id}/report/pdf")

    response = await client.get(f"/v1/scans/{job.id}/report/pdf")

    assert response.status_code == 200
    assert response.json()["status"] == "pending"
    assert response.json()["download_url"] is None


async def test_download_report_pdf_returns_404_before_it_is_rendered(client):
    job, _scan, _account = await _make_completed_scan()
    post_response = await client.post(f"/v1/scans/{job.id}/report/pdf")
    report_id = post_response.json()["report_id"]

    response = await client.get(f"/v1/reports/{report_id}/download")

    assert response.status_code == 404


async def test_download_report_pdf_returns_the_bytes_once_complete(client):
    job, scan, _account = await _make_completed_scan()

    async with session_scope() as session:
        report, _ = await get_or_create_pdf_report(session, scan.id)
        await put_report_pdf(str(report.id), b"%PDF-1.4 fake")
        await mark_report_complete(session, report.id)

    status_response = await client.get(f"/v1/scans/{job.id}/report/pdf")
    assert status_response.json()["status"] == "complete"
    assert status_response.json()["download_url"] == f"/v1/reports/{report.id}/download"

    download_response = await client.get(f"/v1/reports/{report.id}/download")
    assert download_response.status_code == 200
    assert download_response.content == b"%PDF-1.4 fake"
    assert download_response.headers["content-type"] == "application/pdf"
