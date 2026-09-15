"""Turns (Check, CheckResult) pairs into Finding records."""

from __future__ import annotations

import hashlib

from vigilo_checks.registry import Check, CheckResult
from vigilo_core.evidence import EvidenceBundle
from vigilo_core.models import Evidence, Finding, Tier


def _fingerprint(check_id: str, target_origin: str) -> str:
    """`check_id + target_origin` is a Phase-1-appropriate simplification —
    there's no per-path location yet. Extend when Phase 2's `EXP`/`APP`
    categories add path-level findings (docs/build-roadmap.md)."""
    digest = hashlib.sha256(f"{check_id}|{target_origin}".encode()).hexdigest()
    return digest[:16]


def to_findings(
    bundle: EvidenceBundle, results: list[tuple[Check, CheckResult]]
) -> list[Finding]:
    findings: list[Finding] = []
    for check, result in results:
        evidence = None
        if result.matched_indicator:
            evidence = Evidence(
                id=_fingerprint(check.manifest.check_id, bundle.target_origin),
                request_summary=f"GET {bundle.target_origin}",
                response_summary=result.detail,
                matched_indicator=result.matched_indicator,
                redaction_applied=False,
                captured_at=bundle.captured_at,
            )
        findings.append(
            Finding(
                check_id=check.manifest.check_id,
                verdict=result.verdict,
                severity=check.manifest.severity_default,
                confidence=check.manifest.confidence,
                title=check.manifest.title,
                summary=result.detail,
                evidence=evidence,
                fingerprint=_fingerprint(check.manifest.check_id, bundle.target_origin),
            )
        )
    return findings


def run_registry(bundle: EvidenceBundle, registry: list[Check]) -> list[Finding]:
    results = [(check, check.evaluate(bundle)) for check in registry]
    return to_findings(bundle, results)


def plan_registry(registry: list[Check], tier: Tier) -> list[Check]:
    """Check-layer tier gating (docs/adr/ADR-0003-scan-authorization-model.md):
    the checks a scan is *allowed* to evaluate, given its granted tier.
    `run_registry`/`to_findings` produce exactly one `Finding` per check
    passed in, regardless of verdict — an unreachable active-tier check
    isn't safely represented by letting it run and fall back to
    `INCONCLUSIVE` via `@requires()`; it must never be in the list at all.
    Plain equality, matching `resolve_authorization()`'s own idiom — `Tier`
    has exactly two values and every tier comparison elsewhere in this
    codebase already uses equality, not an ordering abstraction."""
    return [
        check
        for check in registry
        if check.manifest.tier_required == Tier.PASSIVE or tier == Tier.ACTIVE
    ]
