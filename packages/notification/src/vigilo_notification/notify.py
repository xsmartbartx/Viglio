"""notify(): renders and delivers whatever `NotificationEvent` it's handed
(docs/modules.md §10 — "no decision logic. It renders and delivers what
monitoring produced."). Delivery failure never raises — mirrors
`run_scan_job`'s existing report-email handling
(`packages/orchestrator/jobs.py`), returned as a `DeliveryResult` instead
so the caller can log/retry without a try/except of its own.
"""

from __future__ import annotations

import httpx

from vigilo_integrations.errors import MailDeliveryFailed
from vigilo_integrations.mail import send_transactional_email
from vigilo_notification.models import DeliveryResult, NotificationEvent
from vigilo_notification.templates import render_digest, render_single


async def notify(
    event: NotificationEvent, transport: httpx.AsyncBaseTransport | None = None
) -> DeliveryResult:
    if not event.occurrences:
        return DeliveryResult(delivered=False, reason="no occurrences to notify")

    if len(event.occurrences) == 1:
        subject, html_body = render_single(event.occurrences[0])
    else:
        subject, html_body = render_digest(event)

    try:
        await send_transactional_email(
            to=event.account_email, subject=subject, html_body=html_body, transport=transport
        )
    except MailDeliveryFailed as exc:
        return DeliveryResult(delivered=False, reason=str(exc))

    return DeliveryResult(delivered=True)
