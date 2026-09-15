"""Remediation cache repository (docs/data-model.md `remediation_cache`,
docs/adr/ADR-0004-llm-boundary.md). Every function takes an already-open
`AsyncSession`, matching every other repository in this codebase.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from vigilo_core.models import Finding
from vigilo_orchestrator.orm import RemediationCacheRow
from vigilo_reporting.models import RemediationPrompt


async def get_remediations_for_findings(
    session: AsyncSession, findings: Iterable[Finding], registry_version: str
) -> dict[str, RemediationPrompt]:
    """One bulk query keyed by fingerprint, returned as a dict keyed by
    `check_id` — the shape `build_report()` wants. Within one scan's
    findings, `check_id` is unique, so no collision is possible."""
    fingerprints = [finding.fingerprint for finding in findings]
    if not fingerprints:
        return {}

    result = await session.execute(
        select(RemediationCacheRow).where(
            RemediationCacheRow.fingerprint.in_(fingerprints),
            RemediationCacheRow.registry_version == registry_version,
        )
    )
    return {
        row.check_id: RemediationPrompt(
            check_id=row.check_id,
            source="llm",
            explanation=row.explanation,
            impact=row.impact,
            remediation_steps=row.remediation_steps,
            agent_prompt=row.agent_prompt,
            estimated_effort=row.estimated_effort,
        )
        for row in result.scalars()
    }


async def cache_remediation(
    session: AsyncSession,
    fingerprint: str,
    check_id: str,
    registry_version: str,
    prompt: RemediationPrompt,
) -> None:
    """No-op unless `prompt.source == "llm"` — template results are free to
    recompute and shouldn't freeze a finding at template quality once the
    provider becomes available. Select-then-insert-or-update, matching
    `reports.get_or_create_pdf_report()`'s existing pattern — no
    dialect-specific upsert exists anywhere else in this codebase."""
    if prompt.source != "llm":
        return

    result = await session.execute(
        select(RemediationCacheRow).where(
            RemediationCacheRow.fingerprint == fingerprint,
            RemediationCacheRow.registry_version == registry_version,
        )
    )
    row = result.scalar_one_or_none()

    fields: dict[str, Any] = {
        "explanation": prompt.explanation,
        "impact": prompt.impact,
        "remediation_steps": prompt.remediation_steps,
        "agent_prompt": prompt.agent_prompt,
        "estimated_effort": prompt.estimated_effort,
    }

    if row is None:
        row = RemediationCacheRow(
            fingerprint=fingerprint,
            check_id=check_id,
            registry_version=registry_version,
            **fields,
        )
        session.add(row)
    else:
        for key, value in fields.items():
            setattr(row, key, value)

    await session.flush()
