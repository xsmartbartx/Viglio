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


class Meter(StrEnum):
    TARGETS = "targets"
    SCANS_MONTHLY = "scans_monthly"
    MONITORS = "monitors"


@dataclass(frozen=True)
class Plan:
    """One subscription plan's static entitlements
    (docs/prooflight-vision-and-architecture.md §14). `None` on a limit
    field means unlimited. `api_keys_limit`/`repo_connectors_limit` are
    Phase 9-shaped but unenforced — no API key or repo connector exists yet
    to restrict. `monitoring_frequency`/`monitors_limit` were the same
    (Phase 8-shaped, unenforced) until Phase 8 wired them up."""

    plan_id: PlanId
    targets_limit: int | None
    scans_per_month_limit: int | None
    active_tier_allowed: bool
    share_links_allowed: bool
    monitoring_frequency: str | None = None
    monitors_limit: int | None = None
    api_keys_limit: int | None = None
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
