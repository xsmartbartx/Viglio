"""interpret_webhook_event(): turns the raw, provider-shaped payload
`vigilo_integrations.billing.parse_webhook_event()` hands back into billing's
own `MoREvent`. Pure — no session, no I/O. Payload field names below match
Paddle's actual webhook contract (`event_type`, `data.subscription_id`,
`data.customer.email`, etc.) — see `packages/integrations/src/
vigilo_integrations/billing.py`'s module docstring for the concrete shape.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from vigilo_billing.errors import UnrecognizedWebhookEvent
from vigilo_billing.models import MoREvent

_RECOGNIZED_EVENT_TYPES = frozenset(
    {
        "subscription.created",
        "subscription.updated",
        "subscription.canceled",
    }
)

_STATUS_BY_EVENT_TYPE = {
    "subscription.created": "active",
    "subscription.updated": "active",
    "subscription.canceled": "canceled",
}


def interpret_webhook_event(payload: dict[str, Any]) -> MoREvent:
    event_type = payload.get("event_type")
    if event_type not in _RECOGNIZED_EVENT_TYPES:
        raise UnrecognizedWebhookEvent(
            "unrecognized billing webhook event type", event_type=str(event_type)
        )

    data = payload.get("data", {})
    period_end_raw = data.get("current_billing_period", {}).get("ends_at")

    try:
        return MoREvent(
            event_type=event_type,
            provider="paddle",
            provider_subscription_id=data["subscription_id"],
            account_email=data["customer"]["email"],
            plan_id=data["plan_id"],
            status=_STATUS_BY_EVENT_TYPE[event_type],
            period_end=datetime.fromisoformat(period_end_raw) if period_end_raw else None,
        )
    except (KeyError, TypeError, ValueError) as exc:
        # A recognized event_type with a malformed/incomplete payload is
        # treated the same as an unrecognized one — discarded whole, never
        # partially applied, same "strict schema or nothing" posture Phase
        # 5's LLM-response handling already established.
        raise UnrecognizedWebhookEvent(
            "malformed billing webhook payload", event_type=event_type
        ) from exc
