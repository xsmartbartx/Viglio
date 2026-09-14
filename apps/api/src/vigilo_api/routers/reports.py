"""`GET /v1/scans/{id}/report` (evidence panels, severity grouping,
skipped-checks transparency — Phase 4's exit criterion) plus PDF export.

The report itself is unauthenticated by design, same posture as Phase 3's
`GET /v1/scans/{id}` — an unguessable UUID is already a de facto share link.
`is_owner` is computed from an *optional* bearer token so the frontend can
show owner-only controls (PDF export, share-link management) without a
second round trip.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from vigilo_identity.models import Account
from vigilo_orchestrator.reports import get_findings_for_scan, get_or_create_pdf_report, get_report_pdf_bytes
from vigilo_orchestrator.service import get_scan_by_job_id, get_scan_job
from vigilo_project.repository import get_or_create_default_project, get_target

from vigilo_api.deps import OptionalAccountDep, QueueDep, SessionDep
from vigilo_api.report_rendering import render_scan_report
from vigilo_api.schemas import PdfStatusResponse, ScanReportResponse

router = APIRouter(tags=["reports"])


async def _is_owner(session: SessionDep, account: Account | None, target_id: uuid.UUID) -> bool:
    if account is None:
        return False
    target = await get_target(session, target_id)
    if target is None:
        return False
    project = await get_or_create_default_project(session, account.id)
    return target.project_id == project.id


@router.get("/v1/scans/{scan_job_id}/report", response_model=ScanReportResponse)
async def get_scan_report(
    scan_job_id: uuid.UUID, session: SessionDep, account: OptionalAccountDep
) -> ScanReportResponse:
    job = await get_scan_job(session, scan_job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="scan not found")

    scan = await get_scan_by_job_id(session, scan_job_id)
    if scan is None:
        raise HTTPException(status_code=409, detail="report not ready")

    target = await get_target(session, job.target_id)
    findings = await get_findings_for_scan(session, scan.id)
    response = render_scan_report(target.origin if target else "", scan, findings)
    response.scan_job_id = scan_job_id
    response.is_owner = await _is_owner(session, account, job.target_id)
    return response


@router.post("/v1/scans/{scan_job_id}/report/pdf", status_code=202, response_model=PdfStatusResponse)
async def request_report_pdf(
    scan_job_id: uuid.UUID, session: SessionDep, queue: QueueDep
) -> PdfStatusResponse:
    scan = await get_scan_by_job_id(session, scan_job_id)
    if scan is None:
        raise HTTPException(status_code=409, detail="report not ready")

    report, should_render = await get_or_create_pdf_report(session, scan.id)
    await session.commit()  # the report row must be durable before the worker can see it

    if should_render:
        await queue.enqueue_job("render_report_pdf_job", str(report.id))

    return PdfStatusResponse(report_id=report.id, status=report.status)


@router.get("/v1/scans/{scan_job_id}/report/pdf", response_model=PdfStatusResponse)
async def get_report_pdf_status(scan_job_id: uuid.UUID, session: SessionDep) -> PdfStatusResponse:
    scan = await get_scan_by_job_id(session, scan_job_id)
    if scan is None:
        raise HTTPException(status_code=409, detail="report not ready")

    report, _ = await get_or_create_pdf_report(session, scan.id)
    download_url = f"/v1/reports/{report.id}/download" if report.status == "complete" else None

    return PdfStatusResponse(report_id=report.id, status=report.status, download_url=download_url)


@router.get("/v1/reports/{report_id}/download")
async def download_report_pdf(report_id: uuid.UUID, session: SessionDep) -> Response:
    # get_report_pdf_bytes() raises ReportNotFound (-> 404 via the app-wide
    # StructuredError handler) for both an unknown id and a not-yet-complete
    # PDF — no separate existence check needed here.
    content = await get_report_pdf_bytes(session, report_id)
    return Response(content=content, media_type="application/pdf")
