from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import vigilo_orchestrator.jobs as jobs
from vigilo_core.evidence import EvidenceBundle
from vigilo_core.models import (
    Confidence,
    Finding,
    Score,
    Severity,
    Tier,
    Verdict,
    VerificationMethod,
)
from vigilo_identity.repository import get_or_create_account
from vigilo_integrations.errors import MailDeliveryFailed
from vigilo_orchestrator.remediation import get_remediations_for_findings
from vigilo_orchestrator.reports import get_or_create_pdf_report, get_report
from vigilo_orchestrator.service import (
    advance,
    create_scan_job,
    get_scan_by_job_id,
    get_scan_job,
    record_scan_result,
)
from vigilo_persistence import session_scope
from vigilo_project.repository import (
    create_target,
    get_or_create_default_project,
    get_target,
    issue_ownership_proof,
)
from vigilo_reporting.errors import PdfRenderError
from vigilo_security.exceptions import EgressDenied
from vigilo_security.ownership import VerificationResult

_FIXTURES_DIR = Path(__file__).resolve().parents[3] / "fixtures" / "golden-targets"


def _load_bundle(name: str) -> EvidenceBundle:
    return EvidenceBundle.model_validate_json((_FIXTURES_DIR / name).read_text(encoding="utf-8"))


async def _make_target(email: str):
    async with session_scope() as session:
        account = await get_or_create_account(session, email=email)
        project = await get_or_create_default_project(session, account.id)
        target = await create_target(session, project.id, "https://example.com")
    return target


async def _make_authorized_job(email: str = "owner@example.com"):
    target = await _make_target(email)
    async with session_scope() as session:
        job = await create_scan_job(session, target.id, Tier.PASSIVE, email, "0.1")
        job = await advance(session, job.id, "authorized")
    return job, target


async def test_run_scan_job_completes_and_persists_a_scan(db_schema, monkeypatch):
    job, _target = await _make_authorized_job()
    sent = {}

    async def fake_run_probes(url, tier=None, **kwargs):
        return _load_bundle("good-config.json")

    async def fake_send_email(to, subject, html_body, **kwargs):
        sent["to"] = to
        sent["subject"] = subject

    monkeypatch.setattr(jobs, "run_probes", fake_run_probes)
    monkeypatch.setattr(jobs, "send_transactional_email", fake_send_email)

    await jobs.run_scan_job({}, str(job.id))

    async with session_scope() as session:
        final = await get_scan_job(session, job.id)
        scan = await get_scan_by_job_id(session, job.id)

    assert final is not None and final.status == "complete"
    assert scan is not None
    assert scan.grade == "A"
    assert sent["to"] == "owner@example.com"


async def test_run_scan_job_marks_unreachable_when_egress_is_denied(db_schema, monkeypatch):
    job, _target = await _make_authorized_job()

    async def fake_run_probes(url, tier=None, **kwargs):
        raise EgressDenied("simulated deny", host="example.com")

    monkeypatch.setattr(jobs, "run_probes", fake_run_probes)

    await jobs.run_scan_job({}, str(job.id))

    async with session_scope() as session:
        final = await get_scan_job(session, job.id)
    assert final is not None and final.status == "unreachable"


async def test_run_scan_job_completes_even_when_email_delivery_fails(db_schema, monkeypatch):
    job, _target = await _make_authorized_job()

    async def fake_run_probes(url, tier=None, **kwargs):
        return _load_bundle("good-config.json")

    async def failing_send(*args, **kwargs):
        raise MailDeliveryFailed("simulated failure")

    monkeypatch.setattr(jobs, "run_probes", fake_run_probes)
    monkeypatch.setattr(jobs, "send_transactional_email", failing_send)

    await jobs.run_scan_job({}, str(job.id))

    async with session_scope() as session:
        final = await get_scan_job(session, job.id)
    assert final is not None and final.status == "complete"


class _FakeRedis:
    def __init__(self) -> None:
        self.enqueued: list[tuple[str, tuple]] = []

    async def enqueue_job(self, function: str, *args) -> None:
        self.enqueued.append((function, args))


async def test_run_scan_job_enqueues_remediation_generation_when_ctx_has_redis(
    db_schema, monkeypatch
):
    job, _target = await _make_authorized_job()

    async def fake_run_probes(url, tier=None, **kwargs):
        return _load_bundle("good-config.json")

    async def fake_send_email(to, subject, html_body, **kwargs):
        return None

    monkeypatch.setattr(jobs, "run_probes", fake_run_probes)
    monkeypatch.setattr(jobs, "send_transactional_email", fake_send_email)

    redis = _FakeRedis()
    await jobs.run_scan_job({"redis": redis}, str(job.id))

    assert redis.enqueued == [("generate_remediations_job", (str(job.id),))]


async def test_run_scan_job_is_a_noop_for_a_job_not_yet_authorized(db_schema):
    target = await _make_target("noop@example.com")
    async with session_scope() as session:
        job = await create_scan_job(session, target.id, Tier.PASSIVE, None, "0.1")

    await jobs.run_scan_job({}, str(job.id))

    async with session_scope() as session:
        final = await get_scan_job(session, job.id)
    assert final is not None and final.status == "queued"


async def test_verify_ownership_job_marks_target_active_on_success(db_schema, monkeypatch):
    target = await _make_target("owner2@example.com")
    async with session_scope() as session:
        proof = await issue_ownership_proof(session, target.id, VerificationMethod.DNS_TXT)

    async def fake_verify_ownership(method, origin, nonce, **kwargs):
        return VerificationResult(
            verified=True, method=method, detail="ok", checked_at=datetime.now(UTC)
        )

    monkeypatch.setattr(jobs, "verify_ownership", fake_verify_ownership)

    await jobs.verify_ownership_job({}, str(proof.id))

    async with session_scope() as session:
        reloaded = await get_target(session, target.id)
    assert reloaded is not None
    assert reloaded.verification_status == Tier.ACTIVE


async def test_verify_ownership_job_does_nothing_on_failure(db_schema, monkeypatch):
    target = await _make_target("owner3@example.com")
    async with session_scope() as session:
        proof = await issue_ownership_proof(session, target.id, VerificationMethod.META_TAG)

    async def fake_verify_ownership(method, origin, nonce, **kwargs):
        return VerificationResult(
            verified=False, method=method, detail="not yet", checked_at=datetime.now(UTC)
        )

    monkeypatch.setattr(jobs, "verify_ownership", fake_verify_ownership)

    await jobs.verify_ownership_job({}, str(proof.id))

    async with session_scope() as session:
        reloaded = await get_target(session, target.id)
    assert reloaded is not None
    assert reloaded.verification_status == Tier.PASSIVE


async def _make_completed_scan(email: str = "owner4@example.com"):
    job, _target = await _make_authorized_job(email)
    async with session_scope() as session:
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
    return scan


async def test_render_report_pdf_job_completes_and_stores_the_pdf(db_schema, monkeypatch):
    scan = await _make_completed_scan()
    async with session_scope() as session:
        report, _should_render = await get_or_create_pdf_report(session, scan.id)

    stored = {}

    async def fake_render_pdf(scan_job_id, **kwargs):
        # apps/web's report route is keyed by the public scan_job_id
        # (Scan.job_id), not the Report row's own id — asserting this here
        # is what would have caught the id-confusion bug this job originally
        # shipped with (it passed report_id straight through, silently
        # rendering apps/web's 404 page instead of the report).
        stored["scan_job_id_arg"] = scan_job_id
        return b"%PDF-1.4 fake"

    async def fake_put_report_pdf(report_id, content):
        stored["report_id"] = report_id
        stored["content"] = content

    monkeypatch.setattr(jobs, "render_pdf", fake_render_pdf)
    monkeypatch.setattr(jobs, "put_report_pdf", fake_put_report_pdf)

    await jobs.render_report_pdf_job({}, str(report.id))

    async with session_scope() as session:
        final = await get_report(session, report.id)
    assert final is not None
    assert final.status == "complete"
    assert final.artefact_uri == str(report.id)
    assert stored["scan_job_id_arg"] == str(scan.job_id)
    assert stored["report_id"] == str(report.id)
    assert stored["content"] == b"%PDF-1.4 fake"


async def test_render_report_pdf_job_marks_failed_on_render_error(db_schema, monkeypatch):
    scan = await _make_completed_scan()
    async with session_scope() as session:
        report, _should_render = await get_or_create_pdf_report(session, scan.id)

    async def failing_render_pdf(scan_job_id, **kwargs):
        raise PdfRenderError("simulated render failure")

    monkeypatch.setattr(jobs, "render_pdf", failing_render_pdf)

    await jobs.render_report_pdf_job({}, str(report.id))

    async with session_scope() as session:
        final = await get_report(session, report.id)
    assert final is not None
    assert final.status == "failed"


async def test_render_report_pdf_job_is_a_noop_for_a_non_pending_report(db_schema, monkeypatch):
    scan = await _make_completed_scan()
    async with session_scope() as session:
        report, _should_render = await get_or_create_pdf_report(session, scan.id)

    async def should_not_be_called(scan_job_id, **kwargs):
        raise AssertionError("render_pdf should not have been called")

    monkeypatch.setattr(jobs, "render_pdf", should_not_be_called)

    # First run completes it (via the success path, but we monkeypatch again
    # to avoid depending on ordering with the test above).
    async def fake_render_pdf(scan_job_id, **kwargs):
        return b"%PDF-1.4 fake"

    monkeypatch.setattr(jobs, "render_pdf", fake_render_pdf)
    await jobs.render_report_pdf_job({}, str(report.id))

    monkeypatch.setattr(jobs, "render_pdf", should_not_be_called)
    await jobs.render_report_pdf_job({}, str(report.id))  # should return early, no error


async def test_generate_remediations_job_caches_llm_results_for_failed_findings(
    db_schema, monkeypatch
):
    scan = await _make_completed_scan()

    async def fake_generate_remediation(finding, manifest, **kwargs):
        from vigilo_reporting.models import RemediationPrompt

        return RemediationPrompt(
            check_id=finding.check_id,
            source="llm",
            explanation="e",
            impact="i",
            remediation_steps=["s"],
            agent_prompt="a",
            estimated_effort="small",
        )

    monkeypatch.setattr(jobs, "generate_remediation", fake_generate_remediation)

    await jobs.generate_remediations_job({}, str(scan.job_id))

    async with session_scope() as session:
        findings = await jobs.get_findings_for_scan(session, scan.id)
        cached = await get_remediations_for_findings(session, findings, scan.registry_version)

    assert cached["VG-HDR-001"].source == "llm"


async def test_generate_remediations_job_skips_findings_already_cached(db_schema, monkeypatch):
    scan = await _make_completed_scan()

    async def should_not_be_called(finding, manifest, **kwargs):
        raise AssertionError("generate_remediation should not have been called")

    async with session_scope() as session:
        from vigilo_orchestrator.remediation import cache_remediation
        from vigilo_reporting.models import RemediationPrompt

        await cache_remediation(
            session,
            "fp1",
            "VG-HDR-001",
            scan.registry_version,
            RemediationPrompt(
                check_id="VG-HDR-001",
                source="llm",
                explanation="already cached",
                impact="i",
                remediation_steps=["s"],
                agent_prompt="a",
                estimated_effort="small",
            ),
        )

    monkeypatch.setattr(jobs, "generate_remediation", should_not_be_called)

    await jobs.generate_remediations_job({}, str(scan.job_id))  # should not raise


async def test_generate_remediations_job_is_a_noop_with_no_failed_findings(db_schema, monkeypatch):
    job, _target = await _make_authorized_job("owner5@example.com")
    async with session_scope() as session:
        job = await advance(session, job.id, "probing")
        job = await advance(session, job.id, "evaluating")
        job = await advance(session, job.id, "scoring")
        score = Score(value=100.0, grade="A", registry_version="0.1", counts_by_severity={})
        scan = await record_scan_result(session, job, [], score, duration_ms=10)

    async def should_not_be_called(finding, manifest, **kwargs):
        raise AssertionError("generate_remediation should not have been called")

    monkeypatch.setattr(jobs, "generate_remediation", should_not_be_called)

    await jobs.generate_remediations_job({}, str(scan.job_id))  # should not raise


async def test_generate_remediations_job_is_a_noop_for_an_unknown_scan_job_id(db_schema):
    await jobs.generate_remediations_job({}, "00000000-0000-0000-0000-000000000000")  # no raise
