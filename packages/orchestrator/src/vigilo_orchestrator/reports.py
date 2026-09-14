"""Report/ShareLink repository (docs/data-model.md), plus
`get_findings_for_scan()` — the direct input `vigilo_reporting.build_report()`
needs, reconstructed from `FindingRow` rows (`Scan.created_at` stands in for
each finding's `captured_at`; see `packages/orchestrator/orm.py`'s module
docstring for why).

Every function takes an already-open `AsyncSession`, matching every other
repository in this codebase.
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from vigilo_core.models import Confidence, Evidence, Finding, Severity, Verdict
from vigilo_integrations.storage import get_report_pdf
from vigilo_orchestrator.errors import ReportNotFound, ShareLinkNotFound
from vigilo_orchestrator.models import Report, ShareLink
from vigilo_orchestrator.orm import FindingRow, ReportRow, ScanRow, ShareLinkRow


async def get_findings_for_scan(session: AsyncSession, scan_id: uuid.UUID) -> list[Finding]:
    scan_row = await session.get(ScanRow, scan_id)
    captured_at = scan_row.created_at if scan_row is not None else datetime.now(UTC)

    result = await session.execute(select(FindingRow).where(FindingRow.scan_id == scan_id))
    findings: list[Finding] = []
    for row in result.scalars():
        evidence = None
        if row.evidence_id is not None:
            evidence = Evidence(
                id=row.evidence_id,
                request_summary=row.request_summary or "",
                response_summary=row.summary,
                matched_indicator=row.matched_indicator or "",
                redaction_applied=bool(row.redaction_applied),
                captured_at=captured_at,
            )
        findings.append(
            Finding(
                check_id=row.check_id,
                verdict=Verdict(row.status),
                severity=Severity(row.severity),
                confidence=Confidence(row.confidence),
                title=row.title,
                summary=row.summary,
                evidence=evidence,
                fingerprint=row.fingerprint,
            )
        )
    return findings


async def _get_report_row(
    session: AsyncSession, scan_id: uuid.UUID, format: str
) -> ReportRow | None:
    result = await session.execute(
        select(ReportRow).where(ReportRow.scan_id == scan_id, ReportRow.format == format)
    )
    return result.scalar_one_or_none()


async def get_or_create_html_report(session: AsyncSession, scan_id: uuid.UUID) -> Report:
    """The HTML "report" is never a stored artefact — its content is always
    computed live from `Scan`/`Finding` rows. This row exists only so a
    `ShareLink` has something to point at."""
    row = await _get_report_row(session, scan_id, "html")
    if row is None:
        row = ReportRow(
            scan_id=scan_id, format="html", status="complete", generated_at=datetime.now(UTC)
        )
        session.add(row)
        await session.flush()
    return Report.model_validate(row)


async def get_or_create_pdf_report(
    session: AsyncSession, scan_id: uuid.UUID
) -> tuple[Report, bool]:
    """Returns `(report, should_render)`. `should_render` is true only when a
    render actually needs to be (re)triggered — a fresh row, or a retry of a
    previously `failed` one — so the caller enqueues `render_report_pdf_job`
    exactly once per real render, matching this module's documented
    idempotence boundary."""
    row = await _get_report_row(session, scan_id, "pdf")
    if row is None:
        row = ReportRow(scan_id=scan_id, format="pdf", status="pending")
        session.add(row)
        await session.flush()
        return Report.model_validate(row), True

    if row.status == "failed":
        row.status = "pending"
        row.artefact_uri = None
        row.generated_at = None
        await session.flush()
        return Report.model_validate(row), True

    return Report.model_validate(row), False


async def get_report(session: AsyncSession, report_id: uuid.UUID) -> Report | None:
    row = await session.get(ReportRow, report_id)
    return Report.model_validate(row) if row else None


async def mark_report_complete(session: AsyncSession, report_id: uuid.UUID) -> Report:
    row = await session.get(ReportRow, report_id)
    if row is None:
        raise ReportNotFound("report not found", report_id=str(report_id))
    row.status = "complete"
    row.artefact_uri = str(report_id)
    row.generated_at = datetime.now(UTC)
    await session.flush()
    return Report.model_validate(row)


async def mark_report_failed(session: AsyncSession, report_id: uuid.UUID) -> Report:
    row = await session.get(ReportRow, report_id)
    if row is None:
        raise ReportNotFound("report not found", report_id=str(report_id))
    row.status = "failed"
    await session.flush()
    return Report.model_validate(row)


async def get_report_pdf_bytes(session: AsyncSession, report_id: uuid.UUID) -> bytes:
    row = await session.get(ReportRow, report_id)
    if row is None or row.status != "complete" or row.artefact_uri is None:
        raise ReportNotFound("report pdf not ready", report_id=str(report_id))
    return await get_report_pdf(row.artefact_uri)


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


async def create_share_link(
    session: AsyncSession, report_id: uuid.UUID, expires_in_days: int | None = None
) -> tuple[ShareLink, str]:
    """Returns `(share_link, plaintext_token)` — the plaintext is returned
    exactly once, at creation, and never persisted (`token_hash` only)."""
    token = secrets.token_urlsafe(32)
    expires_at = (
        datetime.now(UTC) + timedelta(days=expires_in_days) if expires_in_days is not None else None
    )
    row = ShareLinkRow(report_id=report_id, token_hash=_hash_token(token), expires_at=expires_at)
    session.add(row)
    await session.flush()
    return ShareLink.model_validate(row), token


async def list_share_links(session: AsyncSession, report_id: uuid.UUID) -> list[ShareLink]:
    result = await session.execute(select(ShareLinkRow).where(ShareLinkRow.report_id == report_id))
    return [ShareLink.model_validate(row) for row in result.scalars()]


async def get_share_link(session: AsyncSession, share_link_id: uuid.UUID) -> ShareLink | None:
    row = await session.get(ShareLinkRow, share_link_id)
    return ShareLink.model_validate(row) if row else None


async def revoke_share_link(session: AsyncSession, share_link_id: uuid.UUID) -> ShareLink:
    row = await session.get(ShareLinkRow, share_link_id)
    if row is None:
        raise ShareLinkNotFound("share link not found", share_link_id=str(share_link_id))
    row.revoked_at = datetime.now(UTC)
    await session.flush()
    return ShareLink.model_validate(row)


async def resolve_share_link(session: AsyncSession, token: str) -> ShareLink | None:
    """Hash-and-lookup only — does not check `expires_at`/`revoked_at`. The
    caller (an `apps/api` handler) distinguishes "not found" from "expired"
    from "revoked" to return the right HTTP status/message for each."""
    result = await session.execute(
        select(ShareLinkRow).where(ShareLinkRow.token_hash == _hash_token(token))
    )
    row = result.scalar_one_or_none()
    return ShareLink.model_validate(row) if row else None


async def record_share_link_view(session: AsyncSession, share_link_id: uuid.UUID) -> None:
    row = await session.get(ShareLinkRow, share_link_id)
    if row is not None:
        row.view_count += 1
        await session.flush()
