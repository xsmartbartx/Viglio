"""Subject/body rendering. Alert bodies contain finding titles/check ids
and severities only — never evidence, never a secret fingerprint's
location detail (docs/modules.md §10's "no decision logic," including "no
raw evidence"). Every email links to the monitoring dashboard, which
requires an authenticated session — never a direct link into a finding's
evidence panel.
"""

from __future__ import annotations

import uuid

from vigilo_core.config import config
from vigilo_notification.models import AlertOccurrence, NotificationEvent

_SUBJECT_BY_TYPE = {
    "new_critical": "New critical finding on {origin}",
    "new_high": "New high-severity finding on {origin}",
    "regressed": "A previously fixed issue reappeared on {origin}",
    "cert_expiry": "TLS certificate expiring soon on {origin}",
    "score_drop": "Score dropped on {origin}",
    "scan_failed": "A monitored scan failed for {origin}",
}

_DESCRIPTION_BY_TYPE = {
    "new_critical": "A new critical-severity finding was detected",
    "new_high": "A new high-severity finding was detected",
    "regressed": "A previously resolved finding has reappeared",
    "cert_expiry": "The TLS certificate is approaching its expiry date",
    "score_drop": "The score dropped by 10 or more points across two scans",
    "scan_failed": "The scheduled scan could not complete",
}


def _dashboard_url(target_id: uuid.UUID | None) -> str:
    base = config().web_app_url or ""
    return f"{base}/targets/{target_id}/monitoring"


def _occurrence_line(occurrence: AlertOccurrence) -> str:
    description = _DESCRIPTION_BY_TYPE.get(occurrence.event_type, occurrence.event_type)
    detail = occurrence.check_id or occurrence.reason or ""
    return f"<li>{description}{f' ({detail})' if detail else ''}</li>"


def render_single(occurrence: AlertOccurrence) -> tuple[str, str]:
    subject_template = _SUBJECT_BY_TYPE.get(occurrence.event_type, "Vigilo alert for {origin}")
    subject = subject_template.format(origin=occurrence.target_origin)

    description = _DESCRIPTION_BY_TYPE.get(occurrence.event_type, occurrence.event_type)
    detail = f" ({occurrence.check_id})" if occurrence.check_id else ""
    reason = f"<p>{occurrence.reason}</p>" if occurrence.reason else ""
    html_body = (
        f"<h2>{subject}</h2>"
        f"<p>{description}{detail}.</p>"
        f"{reason}"
        f'<p><a href="{_dashboard_url(occurrence.target_id)}">View monitoring dashboard</a></p>'
    )
    return subject, html_body


def render_digest(event: NotificationEvent) -> tuple[str, str]:
    count = len(event.occurrences)
    origin = event.occurrences[0].target_origin if event.occurrences else ""
    subject = f"Vigilo: {count} monitoring alerts for {origin}"

    items = "".join(_occurrence_line(o) for o in event.occurrences)
    target_id = event.occurrences[0].target_id if event.occurrences else None
    html_body = (
        f"<h2>{subject}</h2>"
        f"<ul>{items}</ul>"
        f'<p><a href="{_dashboard_url(target_id)}">View monitoring dashboard</a></p>'
    )
    return subject, html_body
