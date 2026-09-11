"""Structured, sanitized logging. All logging in Vigilo passes through here so
that redaction cannot be bypassed by a caller (docs/modules.md §1).

Callers are expected to have already redacted anything secret-shaped via
`vigilo_core.redact.redact` before it reaches `context`. As defense in depth,
`log()` also strips a fixed set of well-known sensitive key names if a caller
slips up — see docs/architecture.md §12 ("no sensitive data in logs").
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

_SENSITIVE_KEYS = frozenset(
    {
        "password",
        "secret",
        "token",
        "api_key",
        "apikey",
        "authorization",
        "cookie",
        "set-cookie",
        "access_key",
        "secret_key",
    }
)


class Severity(StrEnum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARN = "WARN"
    ERROR = "ERROR"
    SECURITY = "SECURITY"


@dataclass(frozen=True)
class LogEvent:
    """One structured log line. `event` is a dotted name (e.g. "scan.requested"),
    matching the event catalogue in docs/prooflight-vision-and-architecture.md §17.
    """

    event: str
    severity: Severity
    module: str
    context: dict[str, Any] = field(default_factory=dict)


def _sanitize(context: dict[str, Any]) -> dict[str, Any]:
    clean: dict[str, Any] = {}
    for key, value in context.items():
        if key.lower() in _SENSITIVE_KEYS:
            clean[key] = "<REDACTED>"
        elif isinstance(value, dict):
            clean[key] = _sanitize(value)
        else:
            clean[key] = value
    return clean


def log(event: LogEvent) -> None:
    """Emit one structured JSON log line to stdout."""
    record = {
        "timestamp": datetime.now(UTC).isoformat(),
        "event": event.event,
        "severity": event.severity.value,
        "module": event.module,
        "context": _sanitize(event.context),
    }
    print(json.dumps(record, default=str), file=sys.stdout, flush=True)
