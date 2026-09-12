"""Check/CheckResult types and the check registry.

Checks depend on `vigilo_core` only — no I/O, no clock, no randomness
(docs/modules.md §4). This is enforced, not just documented: see
tests/test_import_boundary.py.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from functools import wraps

from vigilo_core.evidence import EvidenceBundle
from vigilo_core.models import CheckManifest, Verdict


@dataclass(frozen=True)
class CheckResult:
    """A single check's verdict against one evidence bundle."""

    verdict: Verdict
    detail: str
    matched_indicator: str | None = None


@dataclass(frozen=True)
class Check:
    manifest: CheckManifest
    evaluate: Callable[[EvidenceBundle], CheckResult]


def get_header(headers: dict[str, str], name: str) -> str | None:
    """Case-insensitive header lookup. Probes store lowercase keys already,
    but checks look this up rather than assume it, so a check never breaks
    if that internal detail changes."""
    return headers.get(name.lower())


def requires(field: str) -> Callable[[Callable[[EvidenceBundle], CheckResult]], Callable]:
    """Decorator: if `bundle.<field>` is None, short-circuit to INCONCLUSIVE
    before calling the wrapped evaluator, per
    docs/prooflight-vision-and-architecture.md §16.3 — "a check that cannot
    find the evidence it declared returns inconclusive, never passed."
    Keeps each check's body focused on its actual condition."""

    def decorator(
        fn: Callable[[EvidenceBundle], CheckResult],
    ) -> Callable[[EvidenceBundle], CheckResult]:
        @wraps(fn)
        def wrapper(bundle: EvidenceBundle) -> CheckResult:
            if getattr(bundle, field) is None:
                return CheckResult(Verdict.INCONCLUSIVE, f"no {field} evidence captured")
            return fn(bundle)

        return wrapper

    return decorator
