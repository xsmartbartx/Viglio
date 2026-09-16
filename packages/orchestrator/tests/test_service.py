from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from vigilo_core.errors import ErrorCode
from vigilo_core.models import Confidence, Finding, Score, Severity, Tier, Verdict
from vigilo_identity.repository import get_or_create_account
from vigilo_orchestrator.errors import InvalidScanTransition, ScanJobNotFound
from vigilo_orchestrator.service import (
    advance,
    create_scan_job,
    get_failed_findings_for_scan,
    get_scan_by_job_id,
    get_scan_job,
    list_ever_failed_fingerprints_before,
    list_scans_for_target,
    record_scan_result,
)
from vigilo_project.repository import create_target, get_or_create_default_project


async def _target_id(session: AsyncSession) -> object:
    account = await get_or_create_account(session, email="owner@example.com")
    project = await get_or_create_default_project(session, account.id)
    target = await create_target(session, project.id, "https://example.com")
    return target.id


async def test_create_scan_job_starts_queued(db_session: AsyncSession) -> None:
    target_id = await _target_id(db_session)

    job = await create_scan_job(db_session, target_id, Tier.PASSIVE, "owner@example.com", "0.1")

    assert job.status == "queued"
    assert job.started_at is None
    assert job.finished_at is None


async def test_valid_transitions_follow_the_documented_state_machine(
    db_session: AsyncSession,
) -> None:
    target_id = await _target_id(db_session)
    job = await create_scan_job(db_session, target_id, Tier.PASSIVE, None, "0.1")

    for status in ["authorized", "probing", "evaluating", "scoring", "reporting", "complete"]:
        job = await advance(db_session, job.id, status)

    assert job.status == "complete"
    assert job.started_at is not None
    assert job.finished_at is not None


async def test_an_illegal_transition_is_rejected(db_session: AsyncSession) -> None:
    target_id = await _target_id(db_session)
    job = await create_scan_job(db_session, target_id, Tier.PASSIVE, None, "0.1")

    try:
        await advance(db_session, job.id, "complete")
        raise AssertionError("expected InvalidScanTransition")
    except InvalidScanTransition as exc:
        assert exc.code == ErrorCode.INVALID_STATE_TRANSITION


async def test_queued_can_be_rejected_instead_of_authorized(db_session: AsyncSession) -> None:
    target_id = await _target_id(db_session)
    job = await create_scan_job(db_session, target_id, Tier.PASSIVE, None, "0.1")

    job = await advance(db_session, job.id, "rejected")

    assert job.status == "rejected"
    assert job.finished_at is not None


async def test_advance_on_an_unknown_job_raises_not_found(db_session: AsyncSession) -> None:
    import uuid

    try:
        await advance(db_session, uuid.uuid4(), "authorized")
        raise AssertionError("expected ScanJobNotFound")
    except ScanJobNotFound as exc:
        assert exc.code == ErrorCode.SCAN_JOB_NOT_FOUND


async def test_get_scan_job_returns_none_for_an_unknown_id(db_session: AsyncSession) -> None:
    import uuid

    assert await get_scan_job(db_session, uuid.uuid4()) is None


def _finding(check_id: str, verdict: Verdict, severity: Severity) -> Finding:
    return Finding(
        check_id=check_id,
        verdict=verdict,
        severity=severity,
        confidence=Confidence.CONFIRMED,
        title="title",
        summary="summary",
        fingerprint=f"fp-{check_id}",
    )


async def test_record_scan_result_persists_the_scan_and_findings(db_session: AsyncSession) -> None:
    target_id = await _target_id(db_session)
    job = await create_scan_job(db_session, target_id, Tier.PASSIVE, "owner@example.com", "0.1")
    job = await advance(db_session, job.id, "authorized")
    job = await advance(db_session, job.id, "probing")
    job = await advance(db_session, job.id, "evaluating")

    findings = [
        _finding("VG-HDR-001", Verdict.FAILED, Severity.HIGH),
        _finding("VG-HDR-002", Verdict.PASSED, Severity.PASSED),
    ]
    result = Score(
        value=72.0, grade="C", registry_version="0.1", counts_by_severity={Severity.HIGH: 1}
    )

    scan = await record_scan_result(
        db_session, job, findings, result, duration_ms=123, bundle_id="abc123"
    )

    assert scan.score == 72.0
    assert scan.grade == "C"
    assert scan.bundle_id == "abc123"

    fetched = await get_scan_by_job_id(db_session, job.id)
    assert fetched is not None
    assert fetched.id == scan.id


async def _completed_scan(session: AsyncSession, target_id, findings: list[Finding], score: float):
    job = await create_scan_job(session, target_id, Tier.PASSIVE, "owner@example.com", "0.1")
    job = await advance(session, job.id, "authorized")
    job = await advance(session, job.id, "probing")
    job = await advance(session, job.id, "evaluating")
    result = Score(value=score, grade="A", registry_version="0.1")
    return await record_scan_result(session, job, findings, result, duration_ms=10)


async def test_list_scans_for_target_returns_most_recent_first(db_session: AsyncSession) -> None:
    target_id = await _target_id(db_session)
    first = await _completed_scan(db_session, target_id, [], 90.0)
    # Commit to close out the transaction Postgres' now() is pinned to —
    # otherwise both scans land in the same still-open transaction and get
    # an identical created_at, making the ordering this test checks
    # non-deterministic (see packages/identity/tests/test_subscriptions.py
    # for the same fix applied to an analogous case).
    await db_session.commit()
    second = await _completed_scan(db_session, target_id, [], 80.0)

    scans = await list_scans_for_target(db_session, target_id)

    assert [s.id for s in scans] == [second.id, first.id]


async def test_list_ever_failed_fingerprints_before_only_looks_strictly_before_the_cutoff(
    db_session: AsyncSession,
) -> None:
    target_id = await _target_id(db_session)
    failing = _finding("VG-HDR-001", Verdict.FAILED, Severity.HIGH)
    passing = _finding("VG-HDR-002", Verdict.PASSED, Severity.PASSED)

    early_scan = await _completed_scan(db_session, target_id, [failing], 60.0)
    cutoff = early_scan.created_at
    await _completed_scan(db_session, target_id, [passing], 90.0)

    fingerprints = await list_ever_failed_fingerprints_before(db_session, target_id, cutoff)
    assert fingerprints == frozenset()

    from datetime import timedelta

    fingerprints_after = await list_ever_failed_fingerprints_before(
        db_session, target_id, cutoff + timedelta(seconds=1)
    )
    assert fingerprints_after == frozenset({failing.fingerprint})


async def test_get_failed_findings_for_scan_filters_to_failed_only(db_session: AsyncSession) -> None:
    target_id = await _target_id(db_session)
    failing = _finding("VG-HDR-001", Verdict.FAILED, Severity.HIGH)
    passing = _finding("VG-HDR-002", Verdict.PASSED, Severity.PASSED)
    scan = await _completed_scan(db_session, target_id, [failing, passing], 70.0)

    result = await get_failed_findings_for_scan(db_session, scan.id)

    assert set(result.keys()) == {failing.fingerprint}
