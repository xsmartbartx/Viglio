"""Vigilo notification: renders and delivers alert emails (docs/modules.md
§10). Depends on core, integrations only.
"""

from __future__ import annotations

from vigilo_notification.models import AlertOccurrence, DeliveryResult, NotificationEvent
from vigilo_notification.notify import notify

__all__ = [
    "AlertOccurrence",
    "NotificationEvent",
    "DeliveryResult",
    "notify",
]
