"""entitlements(): pure resolution of a plan id into its static limits.

Deliberate deviation from docs/modules.md §11's literal
`entitlements(account) -> Entitlements` sketch — matching the precedent
Phase 3 set for `resolve_authorization` and Phase 4 set for `build_report`:
this module has no `persistence`/`identity` dependency, so it cannot
accept an `Account` object. The caller (an `apps/api` handler) reads
whatever `Account.plan_id` it already has and passes the raw string in.
"""

from __future__ import annotations

from vigilo_billing.models import Entitlements, PlanId
from vigilo_billing.plans import PLANS


def entitlements(plan_id: str | None) -> Entitlements:
    """An account with no plan_id (never subscribed) or an unrecognized
    value gets Free's entitlements — fail closed, never fail open into an
    unrestricted plan."""
    try:
        resolved = PlanId(plan_id)
    except ValueError:
        resolved = PlanId.FREE
    return PLANS[resolved]
