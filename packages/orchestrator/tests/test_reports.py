from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from vigilo_core.models import Confidence, Evidence, Finding, Score, Severity, Tier, Verdict
from vigilo_identity.repository import get_or_create_account
from vigilo_orchestrator.errors import ReportNotFound, ShareLinkNotFound
from vigilo_orchestrator.reports import (
    create_share_link,
    get_findings_for_scan,
    get_or_create_html_report,
    get_or_create_pdf_report,
    get_report,
    get_share_link,
    list_share_links,
    mark_report_complete,
    mark_report_failed,
    record_share_link_view,
    resolve_share_link,
    revoke_share_link,
)
from vigilo_orchestrator.service import advance, create_scan_job, record_scan_result
from vigilo_project.repository import create_target, get_or_create_default_project


async def _make_scan(session: AsyncSession, with_evidence: bool = False):
    account = await get_or_create_account(session, email="owner@example.com")
    project = await get_or_create_default_project(session, account.id)
    target = await create_target(session, project.id, "https://example.com")
    job = await create_scan_job(session, target.id, Tier.PASSIVE, "owner@example.com", "0.1")
    job = await advance(session, job.id, "authorized")
    job = await advance(session, job.id, "probing")
    job = await advance(session, job.id, "evaluating")

    evidence = None
    if with_evidence:
        evidence = Evidence(
            id="ev1",
            request_summary="GET https://example.com",
            response_summary="detail",
            matched_indicator="Set-Cookie: session=abc (no Secure)",
            redaction_applied=True,
            captured_at=job.queued_at,
        )
    findings = [
        Finding(
            check_id="VG-HDR-001",
            verdict=Verdict.FAILED,
            severity=Severity.HIGH,
            confidence=Confidence.CONFIRMED,
            title="HSTS enforced",
            summary="No HSTS header present.",
            evidence=evidence,
            fingerprint="fp1",
        )
    ]
    score = Score(
        value=72.0, grade="C", registry_version="0.1", counts_by_severity={Severity.HIGH: 1}
    )
    scan = await record_scan_result(session, job, findings, score, duration_ms=100)
    return scan


async def test_get_findings_for_scan_reconstructs_evidence(db_session: AsyncSession) -> None:
    scan = await _make_scan(db_session, with_evidence=True)

    findings = await get_findings_for_scan(db_session, scan.id)

    assert len(findings) == 1
    assert findings[0].evidence is not None
    assert findings[0].evidence.matched_indicator == "Set-Cookie: session=abc (no Secure)"
    assert findings[0].evidence.redaction_applied is True


async def test_get_findings_for_scan_handles_findings_with_no_evidence(
    db_session: AsyncSession,
) -> None:
    scan = await _make_scan(db_session, with_evidence=False)

    findings = await get_findings_for_scan(db_session, scan.id)

    assert findings[0].evidence is None


async def test_get_or_create_html_report_is_idempotent_and_immediately_complete(
    db_session: AsyncSession,
) -> None:
    scan = await _make_scan(db_session)

    first = await get_or_create_html_report(db_session, scan.id)
    second = await get_or_create_html_report(db_session, scan.id)

    assert first.id == second.id
    assert first.status == "complete"
    assert first.format == "html"


async def test_get_or_create_pdf_report_only_signals_render_on_first_creation(
    db_session: AsyncSession,
) -> None:
    scan = await _make_scan(db_session)

    first, should_render_first = await get_or_create_pdf_report(db_session, scan.id)
    second, should_render_second = await get_or_create_pdf_report(db_session, scan.id)

    assert first.id == second.id
    assert first.status == "pending"
    assert should_render_first is True
    assert should_render_second is False


async def test_get_or_create_pdf_report_retries_after_failure(db_session: AsyncSession) -> None:
    scan = await _make_scan(db_session)
    report, _ = await get_or_create_pdf_report(db_session, scan.id)
    await mark_report_failed(db_session, report.id)

    retried, should_render = await get_or_create_pdf_report(db_session, scan.id)

    assert retried.id == report.id
    assert retried.status == "pending"
    assert should_render is True


async def test_mark_report_complete_sets_artefact_uri_and_generated_at(
    db_session: AsyncSession,
) -> None:
    scan = await _make_scan(db_session)
    report, _ = await get_or_create_pdf_report(db_session, scan.id)

    completed = await mark_report_complete(db_session, report.id)

    assert completed.status == "complete"
    assert completed.artefact_uri == str(report.id)
    assert completed.generated_at is not None


async def test_mark_report_complete_on_an_unknown_report_raises(db_session: AsyncSession) -> None:
    try:
        await mark_report_complete(db_session, uuid.uuid4())
        raise AssertionError("expected ReportNotFound")
    except ReportNotFound:
        pass


async def test_share_link_lifecycle(db_session: AsyncSession) -> None:
    scan = await _make_scan(db_session)
    report = await get_or_create_html_report(db_session, scan.id)

    link, token = await create_share_link(db_session, report.id, expires_in_days=7)
    assert link.expires_at is not None
    assert link.view_count == 0

    links = await list_share_links(db_session, report.id)
    assert [link_row.id for link_row in links] == [link.id]

    resolved = await resolve_share_link(db_session, token)
    assert resolved is not None
    assert resolved.id == link.id

    await record_share_link_view(db_session, link.id)
    reloaded = await get_share_link(db_session, link.id)
    assert reloaded is not None
    assert reloaded.view_count == 1

    revoked = await revoke_share_link(db_session, link.id)
    assert revoked.revoked_at is not None


async def test_resolve_share_link_returns_none_for_an_unknown_token(
    db_session: AsyncSession,
) -> None:
    assert await resolve_share_link(db_session, "not-a-real-token") is None


async def test_revoke_share_link_on_an_unknown_id_raises(db_session: AsyncSession) -> None:
    try:
        await revoke_share_link(db_session, uuid.uuid4())
        raise AssertionError("expected ShareLinkNotFound")
    except ShareLinkNotFound:
        pass


async def test_get_report_returns_none_for_an_unknown_id(db_session: AsyncSession) -> None:
    assert await get_report(db_session, uuid.uuid4()) is None
