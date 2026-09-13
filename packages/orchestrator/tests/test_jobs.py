from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import vigilo_orchestrator.jobs as jobs
from vigilo_core.evidence import EvidenceBundle
from vigilo_core.models import Tier, VerificationMethod
from vigilo_identity.repository import get_or_create_account
from vigilo_integrations.errors import MailDeliveryFailed
from vigilo_orchestrator.service import advance, create_scan_job, get_scan_by_job_id, get_scan_job
from vigilo_persistence import session_scope
from vigilo_project.repository import (
    create_target,
    get_or_create_default_project,
    get_target,
    issue_ownership_proof,
)
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

    async def fake_run_probes(url):
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

    async def fake_run_probes(url):
        raise EgressDenied("simulated deny", host="example.com")

    monkeypatch.setattr(jobs, "run_probes", fake_run_probes)

    await jobs.run_scan_job({}, str(job.id))

    async with session_scope() as session:
        final = await get_scan_job(session, job.id)
    assert final is not None and final.status == "unreachable"


async def test_run_scan_job_completes_even_when_email_delivery_fails(db_schema, monkeypatch):
    job, _target = await _make_authorized_job()

    async def fake_run_probes(url):
        return _load_bundle("good-config.json")

    async def failing_send(*args, **kwargs):
        raise MailDeliveryFailed("simulated failure")

    monkeypatch.setattr(jobs, "run_probes", fake_run_probes)
    monkeypatch.setattr(jobs, "send_transactional_email", failing_send)

    await jobs.run_scan_job({}, str(job.id))

    async with session_scope() as session:
        final = await get_scan_job(session, job.id)
    assert final is not None and final.status == "complete"


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
        return VerificationResult(verified=True, method=method, detail="ok", checked_at=datetime.now(UTC))

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
        return VerificationResult(verified=False, method=method, detail="not yet", checked_at=datetime.now(UTC))

    monkeypatch.setattr(jobs, "verify_ownership", fake_verify_ownership)

    await jobs.verify_ownership_job({}, str(proof.id))

    async with session_scope() as session:
        reloaded = await get_target(session, target.id)
    assert reloaded is not None
    assert reloaded.verification_status == Tier.PASSIVE
