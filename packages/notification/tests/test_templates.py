from __future__ import annotations

import uuid

import pytest

from vigilo_core.config import config
from vigilo_notification.models import AlertOccurrence, NotificationEvent
from vigilo_notification.templates import render_digest, render_single

_TARGET_ID = uuid.uuid4()


@pytest.fixture(autouse=True)
def _web_app_url_configured(monkeypatch):
    monkeypatch.setenv("WEB_APP_URL", "https://app.vigilo.io")
    config.cache_clear()
    yield
    config.cache_clear()


def _occurrence(event_type: str, **overrides) -> AlertOccurrence:
    defaults = dict(
        event_type=event_type,
        target_id=_TARGET_ID,
        target_origin="https://example.com",
        check_id="VG-HDR-001",
        severity="high",
    )
    defaults.update(overrides)
    return AlertOccurrence(**defaults)


def test_render_single_includes_the_target_origin_and_dashboard_link():
    subject, body = render_single(_occurrence("new_critical"))

    assert "https://example.com" in subject
    assert f"https://app.vigilo.io/targets/{_TARGET_ID}/monitoring" in body


def test_render_single_scan_failed_includes_the_reason():
    occurrence = _occurrence("scan_failed", check_id=None, reason="probing timed out")
    _subject, body = render_single(occurrence)

    assert "probing timed out" in body


def test_render_digest_counts_occurrences_in_the_subject():
    event = NotificationEvent(
        account_email="owner@example.com",
        occurrences=[_occurrence("new_high"), _occurrence("regressed")],
    )
    subject, body = render_digest(event)

    assert "2 monitoring alerts" in subject
    assert body.count("<li>") == 2


def test_an_unknown_event_type_still_renders_something_reasonable():
    subject, body = render_single(_occurrence("some_future_type"))

    assert subject
    assert body
