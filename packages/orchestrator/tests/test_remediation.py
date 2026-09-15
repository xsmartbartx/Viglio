from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from vigilo_core.models import Confidence, Finding, Severity, Verdict
from vigilo_orchestrator.remediation import cache_remediation, get_remediations_for_findings
from vigilo_reporting.models import RemediationPrompt


def _finding(check_id: str = "VG-HDR-001", fingerprint: str = "fp1") -> Finding:
    return Finding(
        check_id=check_id,
        verdict=Verdict.FAILED,
        severity=Severity.HIGH,
        confidence=Confidence.CONFIRMED,
        title="HSTS enforced",
        summary="No HSTS header present.",
        fingerprint=fingerprint,
    )


def _llm_prompt(check_id: str = "VG-HDR-001") -> RemediationPrompt:
    return RemediationPrompt(
        check_id=check_id,
        source="llm",
        explanation="explanation",
        impact="impact",
        remediation_steps=["step one", "step two"],
        agent_prompt="agent prompt",
        estimated_effort="small",
    )


async def test_cache_remediation_round_trips_an_llm_result(db_session: AsyncSession) -> None:
    finding = _finding()
    await cache_remediation(db_session, finding.fingerprint, finding.check_id, "0.1", _llm_prompt())

    cached = await get_remediations_for_findings(db_session, [finding], "0.1")

    assert cached["VG-HDR-001"].source == "llm"
    assert cached["VG-HDR-001"].remediation_steps == ["step one", "step two"]
    assert cached["VG-HDR-001"].estimated_effort == "small"


async def test_cache_remediation_is_a_noop_for_a_template_result(db_session: AsyncSession) -> None:
    finding = _finding()
    template_prompt = RemediationPrompt(
        check_id="VG-HDR-001",
        source="template",
        explanation="e",
        impact="i",
        remediation_steps=["s"],
        agent_prompt="a",
        estimated_effort=None,
    )

    await cache_remediation(db_session, finding.fingerprint, finding.check_id, "0.1", template_prompt)

    cached = await get_remediations_for_findings(db_session, [finding], "0.1")
    assert cached == {}


async def test_get_remediations_for_findings_returns_empty_for_no_findings(
    db_session: AsyncSession,
) -> None:
    cached = await get_remediations_for_findings(db_session, [], "0.1")
    assert cached == {}


async def test_get_remediations_for_findings_misses_on_a_different_registry_version(
    db_session: AsyncSession,
) -> None:
    finding = _finding()
    await cache_remediation(db_session, finding.fingerprint, finding.check_id, "0.1", _llm_prompt())

    cached = await get_remediations_for_findings(db_session, [finding], "0.2")

    assert cached == {}


async def test_two_registry_versions_coexist_for_the_same_fingerprint(
    db_session: AsyncSession,
) -> None:
    finding = _finding()
    await cache_remediation(db_session, finding.fingerprint, finding.check_id, "0.1", _llm_prompt())
    await cache_remediation(db_session, finding.fingerprint, finding.check_id, "0.2", _llm_prompt())

    cached_v1 = await get_remediations_for_findings(db_session, [finding], "0.1")
    cached_v2 = await get_remediations_for_findings(db_session, [finding], "0.2")

    assert cached_v1["VG-HDR-001"].source == "llm"
    assert cached_v2["VG-HDR-001"].source == "llm"


async def test_cache_remediation_updates_an_existing_entry_for_the_same_key(
    db_session: AsyncSession,
) -> None:
    finding = _finding()
    await cache_remediation(db_session, finding.fingerprint, finding.check_id, "0.1", _llm_prompt())

    updated = RemediationPrompt(
        check_id="VG-HDR-001",
        source="llm",
        explanation="updated explanation",
        impact="impact",
        remediation_steps=["new step"],
        agent_prompt="agent prompt",
        estimated_effort="large",
    )
    await cache_remediation(db_session, finding.fingerprint, finding.check_id, "0.1", updated)

    cached = await get_remediations_for_findings(db_session, [finding], "0.1")
    assert cached["VG-HDR-001"].explanation == "updated explanation"
    assert cached["VG-HDR-001"].estimated_effort == "large"
