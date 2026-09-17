"""The static plan table (docs/prooflight-vision-and-architecture.md §14),
columns that exist in the product today only — `repo_connectors_limit` is
a deferred feature with nothing to restrict yet (docs/build-roadmap.md's
Phase 9 entry defers the repository connector to its own future phase),
so that field on `Plan` is set but not read by any enforcement code.
`monitors_limit` mirrors each plan's `targets_limit` — one monitor per
target is the natural ceiling, and monitored scans don't consume
`scans_per_month_limit` (docs/build-roadmap.md's Phase 8 entry), so this
is the actual, only cost bound on monitoring. `api_keys_limit` is now
enforced (Phase 9) — every plan sets it explicitly, including Free's `0`,
closing the "unset means unlimited" bug the dataclass default would
otherwise produce. `white_label_allowed` is Business-only, resolving a
contradiction between the vision doc's own §11 artifact table ("Business
tier") and §14 pricing table (which gave it to Studio) — decided in favor
of introducing the Business tier the label actually names.
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
        api_keys_limit=0,
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
        api_rate_limit_per_minute=60,
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
        api_rate_limit_per_minute=300,
        repo_connectors_limit=10,
    ),
    PlanId.BUSINESS: Plan(
        plan_id=PlanId.BUSINESS,
        targets_limit=100,
        scans_per_month_limit=None,
        active_tier_allowed=True,
        share_links_allowed=True,
        monitoring_frequency="daily+custom",
        monitors_limit=100,
        api_keys_limit=100,
        api_rate_limit_per_minute=1000,
        white_label_allowed=True,
        repo_connectors_limit=50,
    ),
}
