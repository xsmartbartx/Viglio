from __future__ import annotations

import httpx
import pytest
from vigilo_core.config import config

from vigilo_integrations.errors import MailDeliveryFailed
from vigilo_integrations.mail import send_transactional_email


@pytest.fixture(autouse=True)
def _postmark_configured(monkeypatch):
    monkeypatch.setenv("POSTMARK_SERVER_TOKEN", "test-token")
    monkeypatch.setenv("MAIL_FROM_ADDRESS", "scans@vigilo.io")
    config.cache_clear()
    yield
    config.cache_clear()


async def test_sends_a_well_formed_request_to_postmark():
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["token"] = request.headers["X-Postmark-Server-Token"]
        return httpx.Response(200, json={"MessageID": "abc"})

    await send_transactional_email(
        to="owner@example.com",
        subject="Your Vigilo scan is ready",
        html_body="<p>Score: 92 (A)</p>",
        transport=httpx.MockTransport(handler),
    )

    assert captured["url"] == "https://api.postmarkapp.com/email"
    assert captured["token"] == "test-token"


async def test_raises_mail_delivery_failed_on_a_rejection():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(422, json={"ErrorCode": 300, "Message": "invalid"})

    with pytest.raises(MailDeliveryFailed):
        await send_transactional_email(
            to="owner@example.com",
            subject="subject",
            html_body="body",
            transport=httpx.MockTransport(handler),
        )


async def test_raises_mail_delivery_failed_on_a_transport_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("simulated connection failure")

    with pytest.raises(MailDeliveryFailed):
        await send_transactional_email(
            to="owner@example.com",
            subject="subject",
            html_body="body",
            transport=httpx.MockTransport(handler),
        )


async def test_raises_when_not_configured(monkeypatch):
    monkeypatch.delenv("POSTMARK_SERVER_TOKEN", raising=False)
    config.cache_clear()

    with pytest.raises(MailDeliveryFailed):
        await send_transactional_email(to="owner@example.com", subject="s", html_body="b")
