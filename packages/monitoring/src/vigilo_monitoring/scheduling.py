"""compute_next_run_at(): pure cadence/jitter/quiet-hours arithmetic
(docs/prooflight-vision-and-architecture.md §10.1). No session, no I/O —
takes `now` as an explicit argument rather than calling `datetime.now()`
itself, so it's deterministically testable.
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta


def _in_quiet_hours(hour: int, quiet_start_utc: int, quiet_end_utc: int) -> bool:
    if quiet_start_utc == quiet_end_utc:
        return False
    if quiet_start_utc < quiet_end_utc:
        return quiet_start_utc <= hour < quiet_end_utc
    # Wraps past midnight, e.g. 22 -> 7.
    return hour >= quiet_start_utc or hour < quiet_end_utc


def compute_next_run_at(
    cadence_hours: int,
    quiet_start_utc: int | None,
    quiet_end_utc: int | None,
    now: datetime,
    jitter_minutes: int = 15,
) -> datetime:
    jitter = timedelta(minutes=random.randint(-jitter_minutes, jitter_minutes))
    candidate = now + timedelta(hours=cadence_hours) + jitter

    if (
        quiet_start_utc is not None
        and quiet_end_utc is not None
        and _in_quiet_hours(candidate.hour, quiet_start_utc, quiet_end_utc)
    ):
        # Push forward to quiet_end_utc — same day if that's still ahead of
        # the candidate (the "early morning" half of a wrapped window),
        # otherwise the next day (the "late night" half).
        pushed = candidate.replace(hour=quiet_end_utc, minute=0, second=0, microsecond=0)
        if pushed <= candidate:
            pushed += timedelta(days=1)
        candidate = pushed

    return candidate
