"""Billing's own types — plain dataclasses, not Pydantic, since this
package never serializes at an HTTP boundary itself (docs/modules.md §11).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class PlanId(StrEnum):
    FREE = "free"
    BUILDER = "builder"
    STUDIO = "studio"
    BUSINESS = "business"


class Meter(StrEnum):
    TARGETS = "targets"
    SCANS_MONTHLY = "scans_monthly"
    MONITORS = "monitors"
    API_KEYS = "api_keys"


@dataclass(frozen=True)
class Plan:
    """One subscription plan's static entitlements
    (docs/prooflight-vision-and-architecture.md §14). `None` on a limit
    field means unlimited — every plan must set `api_keys_limit`
    explicitly rather than relying on that default, since leaving it unset
    on a free-tier plan would silently mean "unlimited API keys," not
    "none" (a real, fixed Phase 9 bug: it was left at this dataclass
    default on Free until API keys were actually enforced).
    `repo_connectors_limit` remains Phase-shaped-but-unenforced — no repo
    connector exists yet to restrict (deferred, `docs/build-roadmap.md`'s
    Phase 9 entry)."""

    plan_id: PlanId
    targets_limit: int | None
    scans_per_month_limit: int | None
    active_tier_allowed: bool
    share_links_allowed: bool
    monitoring_frequency: str | None = None
    monitors_limit: int | None = None
    api_keys_limit: int | None = None
    api_rate_limit_per_minute: int | None = None
    white_label_allowed: bool = False
    repo_connectors_limit: int | None = None


# Same shape as Plan, distinct name — docs/modules.md §11's own sketch
# names the resolved-snapshot type `Entitlements` separately from `Plan`.
Entitlements = Plan


@dataclass(frozen=True)
class QuotaDecision:
    allowed: bool
    current: int
    limit: int | None
    reason: str


@dataclass(frozen=True)
class MoREvent:
    """A merchant-of-record webhook event, normalized to a provider-agnostic
    shape. Built by `interpret_webhook_event()` from the raw payload
    `vigilo_integrations.billing.parse_webhook_event()` hands back."""

    event_type: str
    provider: str
    provider_subscription_id: str
    account_email: str
    plan_id: str
    status: str
    period_end: datetime | None
