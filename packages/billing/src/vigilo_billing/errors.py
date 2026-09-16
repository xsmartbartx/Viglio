from __future__ import annotations

from typing import Any

from vigilo_core.errors import ErrorCode, StructuredError


class QuotaExceeded(StructuredError):
    def __init__(self, message: str, **context: Any) -> None:
        super().__init__(ErrorCode.QUOTA_EXCEEDED, message, **context)


class UnrecognizedWebhookEvent(StructuredError):
    def __init__(self, message: str, **context: Any) -> None:
        super().__init__(ErrorCode.VALIDATION_ERROR, message, **context)
