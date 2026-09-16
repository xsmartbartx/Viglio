from __future__ import annotations

import pytest

from vigilo_billing.errors import UnrecognizedWebhookEvent
from vigilo_billing.webhooks import interpret_webhook_event

_VALID_PAYLOAD = {
    "event_type": "subscription.created",
    "data": {
        "subscription_id": "sub_123",
        "plan_id": "builder",
        "customer": {"email": "owner@example.com"},
        "current_billing_period": {"ends_at": "2026-10-15T00:00:00+00:00"},
    },
}


def test_interpret_webhook_event_maps_a_valid_payload():
    event = interpret_webhook_event(_VALID_PAYLOAD)

    assert event.event_type == "subscription.created"
    assert event.provider == "paddle"
    assert event.provider_subscription_id == "sub_123"
    assert event.account_email == "owner@example.com"
    assert event.plan_id == "builder"
    assert event.status == "active"
    assert event.period_end is not None


def test_interpret_webhook_event_handles_a_canceled_subscription():
    payload = {**_VALID_PAYLOAD, "event_type": "subscription.canceled"}
    event = interpret_webhook_event(payload)
    assert event.status == "canceled"


def test_interpret_webhook_event_tolerates_a_missing_period_end():
    payload = {
        "event_type": "subscription.created",
        "data": {
            "subscription_id": "sub_123",
            "plan_id": "builder",
            "customer": {"email": "owner@example.com"},
        },
    }
    event = interpret_webhook_event(payload)
    assert event.period_end is None


def test_interpret_webhook_event_raises_for_an_unrecognized_event_type():
    payload = {**_VALID_PAYLOAD, "event_type": "invoice.paid"}
    with pytest.raises(UnrecognizedWebhookEvent):
        interpret_webhook_event(payload)


def test_interpret_webhook_event_raises_for_a_malformed_recognized_event():
    payload = {"event_type": "subscription.created", "data": {}}  # missing subscription_id etc.
    with pytest.raises(UnrecognizedWebhookEvent):
        interpret_webhook_event(payload)
