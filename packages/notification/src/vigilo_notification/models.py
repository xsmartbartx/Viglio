"""Plain types `notify()` takes and returns — never a vigilo_monitoring
type (this package never imports vigilo_monitoring, matching the
"notification renders and delivers what monitoring produced" boundary,
docs/modules.md §10). The caller composes an `AlertOccurrence` per event.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass


@dataclass(frozen=True)
class AlertOccurrence:
    event_type: str  # new_critical | new_high | regressed | cert_expiry | score_drop | scan_failed
    target_id: uuid.UUID
    target_origin: str
    check_id: str | None = None
    severity: str | None = None
    reason: str | None = None  # scan_failed's failure reason, or a downgrade notice


@dataclass(frozen=True)
class NotificationEvent:
    """`occurrences` is always a list — one element renders as a single
    alert email, more than one renders as a digest. Whether to batch
    several occurrences into one `NotificationEvent` (the vision doc's
    "more than five events... collapse into a single summary email" rule)
    is `vigilo_monitoring`'s decision, made by how it constructs this
    object — `notify()` itself only picks a rendering, never decides
    whether to batch."""

    account_email: str
    occurrences: list[AlertOccurrence]


@dataclass(frozen=True)
class DeliveryResult:
    delivered: bool
    reason: str | None = None
