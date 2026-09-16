"""The static plan table (docs/prooflight-vision-and-architecture.md §14),
columns that exist in the product today only — API-keys/repo connectors
are Phase 9 features with nothing to restrict yet, so those fields on
`Plan` are set but not read by any enforcement code this phase.
`monitors_limit` mirrors each plan's `targets_limit` — one monitor per
target is the natural ceiling, and monitored scans don't consume
`scans_per_month_limit` (docs/build-roadmap.md's Phase 8 entry), so this
is the actual, only cost bound on monitoring.
"""

from __future__ import annotations

from vigilo_billing.models import Plan, PlanId

PLANS: dict[PlanId, Plan] = {
    PlanId.FREE: Plan(
        plan_id=PlanId.FREE,
        targets_limit=1,
        scans_per_month_limit=3,
        active_tier_allowed=False,
        share_links_allowed=False,
        monitors_limit=0,
    ),
    PlanId.BUILDER: Plan(
        plan_id=PlanId.BUILDER,
        targets_limit=3,
        scans_per_month_limit=100,
        active_tier_allowed=True,
        share_links_allowed=True,
        monitoring_frequency="weekly",
        monitors_limit=3,
        api_keys_limit=1,
        repo_connectors_limit=1,
    ),
    PlanId.STUDIO: Plan(
        plan_id=PlanId.STUDIO,
        targets_limit=25,
        scans_per_month_limit=None,
        active_tier_allowed=True,
        share_links_allowed=True,
        monitoring_frequency="daily+custom",
        monitors_limit=25,
        api_keys_limit=25,
        repo_connectors_limit=10,
    ),
}
