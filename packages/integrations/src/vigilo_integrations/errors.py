from __future__ import annotations

from typing import Any

from vigilo_core.errors import ErrorCode, StructuredError


class MailDeliveryFailed(StructuredError):
    def __init__(self, message: str, **context: Any) -> None:
        super().__init__(ErrorCode.MAIL_DELIVERY_FAILED, message, **context)


class ObjectStoreError(StructuredError):
    def __init__(self, message: str, **context: Any) -> None:
        super().__init__(ErrorCode.OBJECT_STORE_ERROR, message, **context)
