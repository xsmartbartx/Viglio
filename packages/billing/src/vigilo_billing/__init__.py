"""Vigilo billing: map subscription state to entitlements, and decide quota
(docs/modules.md §11).

Every function here is pure and depends on `core` only — no `persistence`,
no `identity` — enforced by `tests/test_import_boundary.py`, not just
documented. This is a deliberate deviation from §11's literal
`entitlements(account) -> Entitlements`/`consume(account, meter, amount)`
sketch, matching the precedent Phase 3 set for `resolve_authorization` and
Phase 4 set for `build_report`: the caller (an `apps/api` handler) fetches
whatever `Account`/usage-count state it needs and passes plain values in.
`Subscription` persistence lives in `packages/identity`, not here.
"""

from __future__ import annotations

from vigilo_billing.entitlements import entitlements
from vigilo_billing.errors import QuotaExceeded, UnrecognizedWebhookEvent
from vigilo_billing.models import Entitlements, Meter, MoREvent, Plan, PlanId, QuotaDecision
from vigilo_billing.plans import PLANS
from vigilo_billing.quota import consume
from vigilo_billing.webhooks import interpret_webhook_event

__all__ = [
    "PlanId",
    "Meter",
    "Plan",
    "Entitlements",
    "QuotaDecision",
    "MoREvent",
    "PLANS",
    "entitlements",
    "consume",
    "interpret_webhook_event",
    "QuotaExceeded",
    "UnrecognizedWebhookEvent",
]
