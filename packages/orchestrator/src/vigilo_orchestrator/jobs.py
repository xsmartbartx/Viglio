"""ARQ task bodies, registered by `apps/scanner`'s `WorkerSettings`. Runs
inside the isolated scan-zone worker process — never called from `apps/api`.

`_evaluate()` duplicates the ~10-line `run_registry` + `compute_score` glue
from `apps/cli/src/vigilo_cli/pipeline.py`'s `evaluate()` rather than
depending on an app package from here (apps don't depend on apps) — a
small, deliberate duplication, not a shared abstraction worth building for
two call sites.
"""

from __future__ import annotations

import time
import uuid
from typing import Any

from vigilo_checks import REGISTRY, run_registry
from vigilo_core.evidence import EvidenceBundle
from vigilo_core.logging import LogEvent, log
from vigilo_core.logging import Severity as LogSeverity
from vigilo_core.models import Finding, Score, Verdict, VerificationMethod
from vigilo_core.validation import ValidationError
from vigilo_integrations.errors import MailDeliveryFailed, ObjectStoreError
from vigilo_integrations.mail import send_transactional_email
from vigilo_integrations.storage import put_evidence_bundle, put_report_pdf
from vigilo_orchestrator.reports import get_report, mark_report_complete, mark_report_failed
from vigilo_orchestrator.service import advance, get_scan, get_scan_job, record_scan_result
from vigilo_persistence import session_scope
from vigilo_probes import run_probes
from vigilo_project.repository import get_ownership_proof, get_target, mark_proof_verified
from vigilo_reporting.errors import PdfRenderError
from vigilo_reporting.pdf import render_pdf
from vigilo_scoring import score as compute_score
from vigilo_security.audit import AuditEvent, audit
from vigilo_security.exceptions import EgressDenied
from vigilo_security.ownership import verify_ownership

REGISTRY_VERSION = "0.1"
_MODULE = "vigilo_orchestrator"


def _evaluate(bundle: EvidenceBundle) -> tuple[list[Finding], Score]:
    findings = run_registry(bundle, REGISTRY)
    manifests_by_id = {check.manifest.check_id: check.manifest for check in REGISTRY}
    result = compute_score(findings, manifests_by_id, REGISTRY_VERSION)
    return findings, result


def _render_report_email(
    target_origin: str, result: Score, findings: list[Finding]
) -> tuple[str, str]:
    failed = [f for f in findings if f.verdict == Verdict.FAILED]
    top = sorted(failed, key=lambda f: f.severity.value)[:5]

    lines = [f"<h2>Vigilo scan report: {target_origin}</h2>"]
    lines.append(f"<p><strong>Score: {result.value:.0f} (grade {result.grade})</strong></p>")
    if top:
        lines.append("<p>Top findings:</p><ul>")
        for finding in top:
            lines.append(f"<li>[{finding.severity.value.upper()}] {finding.title}</li>")
        lines.append("</ul>")
    else:
        lines.append("<p>No failed checks.</p>")

    html_body = "\n".join(lines)
    subject = f"Your Vigilo scan of {target_origin}: {result.grade} ({result.value:.0f}/100)"
    return subject, html_body


async def run_scan_job(ctx: dict[str, Any], scan_job_id: str) -> None:
    job_uuid = uuid.UUID(scan_job_id)
    started = time.monotonic()

    async with session_scope() as session:
        job = await get_scan_job(session, job_uuid)
        if job is None or job.status != "authorized":
            return
        target = await get_target(session, job.target_id)
        if target is None:
            return
        await advance(session, job_uuid, "probing")

    try:
        bundle = await run_probes(target.origin)
    except (EgressDenied, ValidationError) as exc:
        async with session_scope() as session:
            await advance(session, job_uuid, "unreachable")
            await audit(
                session,
                AuditEvent(
                    actor="scanner",
                    action="scan_execution_denied",
                    subject=target.origin,
                    metadata={"reason": str(exc)},
                ),
            )
        log(
            LogEvent(
                event="scan.unreachable",
                severity=LogSeverity.WARN,
                module=_MODULE,
                context={"scan_job_id": scan_job_id, "target": target.origin},
            )
        )
        return
    except Exception:
        async with session_scope() as session:
            await advance(session, job_uuid, "failed")
        log(
            LogEvent(
                event="scan.probing_failed",
                severity=LogSeverity.ERROR,
                module=_MODULE,
                context={"scan_job_id": scan_job_id},
            )
        )
        return

    async with session_scope() as session:
        await advance(session, job_uuid, "evaluating")

    try:
        findings, result = _evaluate(bundle)
    except Exception:
        async with session_scope() as session:
            await advance(session, job_uuid, "failed")
        log(
            LogEvent(
                event="scan.evaluating_failed",
                severity=LogSeverity.ERROR,
                module=_MODULE,
                context={"scan_job_id": scan_job_id},
            )
        )
        return

    bundle_id: str | None = None
    try:
        await put_evidence_bundle(bundle.bundle_id, bundle.model_dump_json().encode())
        bundle_id = bundle.bundle_id
    except ObjectStoreError:
        log(
            LogEvent(
                event="scan.evidence_store_failed",
                severity=LogSeverity.WARN,
                module=_MODULE,
                context={"scan_job_id": scan_job_id},
            )
        )

    duration_ms = int((time.monotonic() - started) * 1000)
    async with session_scope() as session:
        await advance(session, job_uuid, "scoring")
        await record_scan_result(session, job, findings, result, duration_ms, bundle_id=bundle_id)
        await advance(session, job_uuid, "reporting")

    if job.requested_by:
        subject, html_body = _render_report_email(target.origin, result, findings)
        try:
            await send_transactional_email(
                to=job.requested_by, subject=subject, html_body=html_body
            )
        except MailDeliveryFailed:
            log(
                LogEvent(
                    event="scan.report_email_failed",
                    severity=LogSeverity.ERROR,
                    module=_MODULE,
                    context={"scan_job_id": scan_job_id},
                )
            )

    async with session_scope() as session:
        await advance(session, job_uuid, "complete")


async def verify_ownership_job(ctx: dict[str, Any], proof_id: str) -> None:
    proof_uuid = uuid.UUID(proof_id)

    async with session_scope() as session:
        proof = await get_ownership_proof(session, proof_uuid)
        if proof is None:
            return
        target = await get_target(session, proof.target_id)
        if target is None:
            return

    result = await verify_ownership(VerificationMethod(proof.method), target.origin, proof.nonce)

    if not result.verified:
        log(
            LogEvent(
                event="ownership.not_yet_verified",
                severity=LogSeverity.INFO,
                module=_MODULE,
                context={"proof_id": proof_id, "method": proof.method},
            )
        )
        return

    async with session_scope() as session:
        await mark_proof_verified(session, proof_uuid)
        await audit(
            session,
            AuditEvent(
                actor="scanner",
                action="ownership_verified",
                subject=target.origin,
                metadata={"method": proof.method, "proof_id": proof_id},
            ),
        )


async def render_report_pdf_job(ctx: dict[str, Any], report_id: str) -> None:
    """Navigates the live `apps/web` report page with Playwright
    (`vigilo_reporting.render_pdf`) and stores the result. Idempotency
    guard mirrors `run_scan_job`'s: only proceeds if the report is still
    `pending` — `packages/orchestrator/reports.py`'s
    `get_or_create_pdf_report()` is what decides whether to enqueue this in
    the first place."""
    report_uuid = uuid.UUID(report_id)

    async with session_scope() as session:
        report = await get_report(session, report_uuid)
        if report is None or report.status != "pending":
            return
        scan = await get_scan(session, report.scan_id)
        if scan is None:
            return

    try:
        # apps/web's report route is keyed by the public scan_job_id
        # (Scan.job_id), not this Report row's own id — render_pdf() builds
        # its Playwright navigation URL from whatever it's given, so passing
        # the wrong id silently renders apps/web's 404 page instead of the
        # report (no exception, just a one-page PDF of "not found").
        pdf_bytes = await render_pdf(str(scan.job_id))
        await put_report_pdf(report_id, pdf_bytes)
    except (PdfRenderError, ObjectStoreError):
        async with session_scope() as session:
            await mark_report_failed(session, report_uuid)
        log(
            LogEvent(
                event="report.pdf_render_failed",
                severity=LogSeverity.ERROR,
                module=_MODULE,
                context={"report_id": report_id},
            )
        )
        return

    async with session_scope() as session:
        await mark_report_complete(session, report_uuid)
