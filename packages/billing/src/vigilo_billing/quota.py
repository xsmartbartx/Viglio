"""consume(): pure quota comparison. Deliberately does not store or
decrement a balance — every call recomputes `current_usage` fresh from
whatever table actually owns the counted rows (the caller's job, not
billing's — see docs/adr's Phase 7 addendum), so there is no separate
counter that can ever drift out of sync with reality.
"""

from __future__ import annotations

from vigilo_billing.models import Entitlements, Meter, QuotaDecision

_LIMIT_FIELD: dict[Meter, str] = {
    Meter.TARGETS: "targets_limit",
    Meter.SCANS_MONTHLY: "scans_per_month_limit",
}


def consume(
    current_usage: int, amount: int, meter: Meter, entitlements: Entitlements
) -> QuotaDecision:
    """Never raises — mirrors `resolve_authorization()` always returning a
    decision object; the caller decides whether to construct and raise
    `QuotaExceeded`."""
    limit = getattr(entitlements, _LIMIT_FIELD[meter])

    if limit is None:
        return QuotaDecision(allowed=True, current=current_usage, limit=None, reason="unlimited")

    allowed = current_usage + amount <= limit
    reason = "within quota" if allowed else f"{meter.value} limit reached for plan"
    return QuotaDecision(allowed=allowed, current=current_usage, limit=limit, reason=reason)
