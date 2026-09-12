"""The scoring algorithm, implemented literally from
docs/prooflight-vision-and-architecture.md §7.3:

1. Start at 100.
2. For each FAILED finding: deduction = weight × severity_multiplier × confidence_factor.
3. Sum the deductions.
4. Clamp the total to [0, 100].
5. Grade bands: A >= 90, B >= 75, C >= 60, D >= 40, F < 40.

`INCONCLUSIVE`/`NOT_APPLICABLE`/`PASSED` findings contribute no deduction —
they are excluded from affecting the score at all, which is the substance of
the doc's "excluded from the denominator" even though this formula has no
denominator term. Pure function: no I/O, no clock, no randomness — that
purity is what makes a scan of the same evidence always produce the same
score (docs/architecture.md §8).
"""

from __future__ import annotations

from vigilo_core.models import CheckManifest, Confidence, Finding, Score, Severity, Verdict

_SEVERITY_MULTIPLIER: dict[Severity, float] = {
    Severity.CRITICAL: 1.0,
    Severity.HIGH: 0.6,
    Severity.MEDIUM: 0.3,
    Severity.LOW: 0.1,
    Severity.INFO: 0.0,
    Severity.PASSED: 0.0,
}

_CONFIDENCE_FACTOR: dict[Confidence, float] = {
    Confidence.CONFIRMED: 1.0,
    Confidence.INDICATED: 0.5,
}

_GRADE_BANDS: list[tuple[float, str]] = [
    (90.0, "A"),
    (75.0, "B"),
    (60.0, "C"),
    (40.0, "D"),
    (0.0, "F"),
]


def _grade_for(value: float) -> str:
    for threshold, grade in _GRADE_BANDS:
        if value >= threshold:
            return grade
    return "F"  # unreachable: the last band's threshold is 0.0


def score(
    findings: list[Finding],
    manifests_by_id: dict[str, CheckManifest],
    registry_version: str,
) -> Score:
    total_deduction = 0.0
    counts_by_severity: dict[Severity, int] = {}

    for finding in findings:
        if finding.verdict != Verdict.FAILED:
            continue

        counts_by_severity[finding.severity] = counts_by_severity.get(finding.severity, 0) + 1

        manifest = manifests_by_id[finding.check_id]
        deduction = (
            manifest.weight
            * _SEVERITY_MULTIPLIER[finding.severity]
            * _CONFIDENCE_FACTOR[finding.confidence]
        )
        total_deduction += deduction

    value = max(0.0, min(100.0, 100.0 - total_deduction))

    return Score(
        value=value,
        grade=_grade_for(value),
        registry_version=registry_version,
        counts_by_severity=counts_by_severity,
    )
