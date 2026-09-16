from __future__ import annotations

import uuid

import httpx
import pytest

from vigilo_core.config import config
from vigilo_notification.models import AlertOccurrence, NotificationEvent
from vigilo_notification.notify import notify

_TARGET_ID = uuid.uuid4()


@pytest.fixture(autouse=True)
def _postmark_configured(monkeypatch):
    monkeypatch.setenv("POSTMARK_SERVER_TOKEN", "test-token")
    monkeypatch.setenv("MAIL_FROM_ADDRESS", "alerts@vigilo.io")
    monkeypatch.setenv("WEB_APP_URL", "https://app.vigilo.io")
    config.cache_clear()
    yield
    config.cache_clear()


def _occurrence(event_type: str = "regressed") -> AlertOccurrence:
    return AlertOccurrence(
        event_type=event_type,
        target_id=_TARGET_ID,
        target_origin="https://example.com",
        check_id="VG-HDR-001",
        severity="high",
    )


async def test_notify_sends_a_single_alert_email():
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = request.content.decode()
        return httpx.Response(200, json={"MessageID": "abc"})

    event = NotificationEvent(account_email="owner@example.com", occurrences=[_occurrence()])
    result = await notify(event, transport=httpx.MockTransport(handler))

    assert result.delivered is True
    assert "reappeared" in captured["body"]
    assert "https://app.vigilo.io/targets/" in captured["body"]


async def test_notify_sends_a_digest_email_for_multiple_occurrences():
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = request.content.decode()
        return httpx.Response(200, json={"MessageID": "abc"})

    occurrences = [_occurrence("new_high"), _occurrence("regressed"), _occurrence("score_drop")]
    event = NotificationEvent(account_email="owner@example.com", occurrences=occurrences)
    result = await notify(event, transport=httpx.MockTransport(handler))

    assert result.delivered is True
    assert "3 monitoring alerts" in captured["body"]


async def test_notify_returns_a_failed_delivery_result_instead_of_raising():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(422, json={"ErrorCode": 300, "Message": "invalid"})

    event = NotificationEvent(account_email="owner@example.com", occurrences=[_occurrence()])
    result = await notify(event, transport=httpx.MockTransport(handler))

    assert result.delivered is False
    assert result.reason is not None


async def test_notify_with_no_occurrences_does_not_send_anything():
    event = NotificationEvent(account_email="owner@example.com", occurrences=[])
    result = await notify(event)

    assert result.delivered is False
