"""Managed report sharing: hashed, expiring, revocable tokens
(`docs/data-model.md`'s `share_links` table) — additive on top of the base
no-login `GET /v1/scans/{id}/report` access, not a replacement for it. Only
an account that owns the underlying target can issue or revoke a link;
resolving one is public.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException

from vigilo_api.deps import AccountDep, SessionDep
from vigilo_api.report_rendering import render_scan_report
from vigilo_api.schemas import (
    ScanReportResponse,
    ShareLinkCreate,
    ShareLinkCreateResponse,
    ShareLinkResponse,
    ShareLinkRevokeResponse,
)
from vigilo_core.errors import ErrorCode, StructuredError
from vigilo_identity.models import Account
from vigilo_orchestrator.reports import (
    create_share_link,
    get_findings_for_scan,
    get_or_create_html_report,
    get_report,
    get_share_link,
    list_share_links,
    record_share_link_view,
    resolve_share_link,
    revoke_share_link,
)
from vigilo_orchestrator.service import get_scan, get_scan_by_job_id, get_scan_job
from vigilo_project.repository import get_or_create_default_project, get_target

router = APIRouter(tags=["share-links"])


async def _owned_scan_or_404(session: SessionDep, account: Account, scan_job_id: uuid.UUID):
    job = await get_scan_job(session, scan_job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="scan not found")
    target = await get_target(session, job.target_id)
    project = await get_or_create_default_project(session, account.id)
    if target is None or target.project_id != project.id:
        raise HTTPException(status_code=404, detail="scan not found")
    return job


async def _owned_share_link_or_404(session: SessionDep, account: Account, share_link_id: uuid.UUID):
    link = await get_share_link(session, share_link_id)
    if link is None:
        raise HTTPException(status_code=404, detail="share link not found")
    report = await get_report(session, link.report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="share link not found")
    scan = await get_scan(session, report.scan_id)
    if scan is None:
        raise HTTPException(status_code=404, detail="share link not found")
    target = await get_target(session, scan.target_id)
    project = await get_or_create_default_project(session, account.id)
    if target is None or target.project_id != project.id:
        raise HTTPException(status_code=404, detail="share link not found")
    return link


@router.post(
    "/v1/scans/{scan_job_id}/share-links", status_code=201, response_model=ShareLinkCreateResponse
)
async def create_scan_share_link(
    scan_job_id: uuid.UUID,
    body: ShareLinkCreate,
    account: AccountDep,
    session: SessionDep,
) -> ShareLinkCreateResponse:
    await _owned_scan_or_404(session, account, scan_job_id)
    scan = await get_scan_by_job_id(session, scan_job_id)
    if scan is None:
        raise HTTPException(status_code=409, detail="report not ready")

    report = await get_or_create_html_report(session, scan.id)
    link, token = await create_share_link(session, report.id, body.expires_in_days)

    return ShareLinkCreateResponse(
        share_link_id=link.id,
        token=token,
        url=f"/share/{token}",
        expires_at=link.expires_at,
    )


@router.get("/v1/scans/{scan_job_id}/share-links", response_model=list[ShareLinkResponse])
async def list_scan_share_links(
    scan_job_id: uuid.UUID, account: AccountDep, session: SessionDep
) -> list[ShareLinkResponse]:
    await _owned_scan_or_404(session, account, scan_job_id)
    scan = await get_scan_by_job_id(session, scan_job_id)
    if scan is None:
        return []

    report = await get_or_create_html_report(session, scan.id)
    links = await list_share_links(session, report.id)
    return [
        ShareLinkResponse(
            share_link_id=link.id,
            expires_at=link.expires_at,
            revoked_at=link.revoked_at,
            view_count=link.view_count,
            created_at=link.created_at,
        )
        for link in links
    ]


@router.post("/v1/share-links/{share_link_id}/revoke", response_model=ShareLinkRevokeResponse)
async def revoke_scan_share_link(
    share_link_id: uuid.UUID, account: AccountDep, session: SessionDep
) -> ShareLinkRevokeResponse:
    await _owned_share_link_or_404(session, account, share_link_id)
    revoked = await revoke_share_link(session, share_link_id)
    return ShareLinkRevokeResponse(share_link_id=revoked.id, revoked_at=revoked.revoked_at)


@router.get("/v1/share/{token}", response_model=ScanReportResponse)
async def resolve_share(token: str, session: SessionDep) -> ScanReportResponse:
    link = await resolve_share_link(session, token)
    if link is None:
        raise StructuredError(ErrorCode.SHARE_LINK_NOT_FOUND, "share link not found")
    if link.revoked_at is not None:
        raise StructuredError(ErrorCode.SHARE_LINK_REVOKED, "share link has been revoked")
    if link.expires_at is not None and link.expires_at < datetime.now(UTC):
        raise StructuredError(ErrorCode.SHARE_LINK_EXPIRED, "share link has expired")

    report = await get_report(session, link.report_id)
    if report is None:
        raise StructuredError(ErrorCode.SHARE_LINK_NOT_FOUND, "share link not found")
    scan = await get_scan(session, report.scan_id)
    if scan is None:
        raise StructuredError(ErrorCode.SHARE_LINK_NOT_FOUND, "share link not found")

    target = await get_target(session, scan.target_id)
    findings = await get_findings_for_scan(session, scan.id)
    response = render_scan_report(target.origin if target else "", scan, findings)

    await record_share_link_view(session, link.id)
    return response
