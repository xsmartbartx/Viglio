"""Build-blocking proof of Phase 6's exit criterion
(docs/build-roadmap.md): "no active-tier check is reachable against an
unverified target under any code path." Runs as its own CI job
(`tier-gating-suite`, `.github/workflows/ci.yml`), the same standard as
`egress-guard-suite`/`ownership-verification-suite`.

Both directions are asserted, not just the negative — a bug that made
active-tier gating unconditional (an inverted condition, `tier` silently
dropped somewhere) would make a negative-only test pass vacuously.
`run_probes` is monkeypatched to return `bad-config.json`'s bundle
regardless of the tier it's called with — its `paths.detected` is already
populated with a real hit for every one of the 7 active-tier EXP checks —
so a passive-tier job seeing zero active findings actually proves the gate
works, rather than proving the fixture happened to have nothing to find.
"""

from __future__ import annotations

from pathlib import Path

import vigilo_orchestrator.jobs as jobs
from vigilo_core.evidence import EvidenceBundle
from vigilo_core.models import Tier
from vigilo_identity.repository import get_or_create_account
from vigilo_orchestrator.reports import get_findings_for_scan
from vigilo_orchestrator.service import advance, create_scan_job, get_scan_by_job_id
from vigilo_persistence import session_scope
from vigilo_project.repository import create_target, get_or_create_default_project

_FIXTURES_DIR = Path(__file__).resolve().parents[3] / "fixtures" / "golden-targets"
_ACTIVE_EXP_IDS = {f"VG-EXP-{n:03d}" for n in range(6, 13)}


def _load_bundle(name: str) -> EvidenceBundle:
    return EvidenceBundle.model_validate_json((_FIXTURES_DIR / name).read_text(encoding="utf-8"))


async def _make_authorized_job(email: str, tier: Tier):
    async with session_scope() as session:
        account = await get_or_create_account(session, email=email)
        project = await get_or_create_default_project(session, account.id)
        target = await create_target(session, project.id, "https://example.com")
        job = await create_scan_job(session, target.id, tier, email, "0.1")
        job = await advance(session, job.id, "authorized")
    return job


async def _run_and_collect_findings(job, monkeypatch) -> tuple[Tier | None, list]:
    received_tier: dict[str, Tier | None] = {"value": None}

    async def fake_run_probes(url, tier=None, **kwargs):
        received_tier["value"] = tier
        return _load_bundle("bad-config.json")

    async def fake_send_email(*args, **kwargs):
        return None

    monkeypatch.setattr(jobs, "run_probes", fake_run_probes)
    monkeypatch.setattr(jobs, "send_transactional_email", fake_send_email)

    await jobs.run_scan_job({}, str(job.id))

    async with session_scope() as session:
        scan = await get_scan_by_job_id(session, job.id)
        findings = await get_findings_for_scan(session, scan.id)

    return received_tier["value"], findings


async def test_a_passive_tier_job_never_produces_active_tier_findings(db_schema, monkeypatch):
    job = await _make_authorized_job("passive-proof@example.com", Tier.PASSIVE)

    received_tier, findings = await _run_and_collect_findings(job, monkeypatch)

    assert received_tier == Tier.PASSIVE
    found_active_ids = {f.check_id for f in findings if f.check_id in _ACTIVE_EXP_IDS}
    assert found_active_ids == set()


async def test_an_active_tier_job_does_produce_active_tier_findings(db_schema, monkeypatch):
    """The positive counterpart — proves the gate isn't just permanently
    closed."""
    job = await _make_authorized_job("active-proof@example.com", Tier.ACTIVE)

    received_tier, findings = await _run_and_collect_findings(job, monkeypatch)

    assert received_tier == Tier.ACTIVE
    found_active_ids = {f.check_id for f in findings if f.check_id in _ACTIVE_EXP_IDS}
    assert found_active_ids == _ACTIVE_EXP_IDS
