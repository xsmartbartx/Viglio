"""Vigilo scoring: turn a finding set into a versioned, deterministic score
and grade (docs/modules.md §5). Consumes findings only — never reads
evidence, never re-evaluates a check, no I/O, no clock, no randomness.

`compare(previous, current) -> Delta` is part of this module's eventual
public API per docs/modules.md §5, but belongs with Phase 8 (monitoring/
diffing, docs/build-roadmap.md) — nothing before that phase has two scores
to compare yet, so it's not implemented here.
"""

from vigilo_scoring.score import score

__all__ = ["score"]
