from __future__ import annotations

from typing import Any

from vigilo_core.errors import ErrorCode, StructuredError


class EgressDenied(StructuredError):
    """Raised when a target, or a redirect hop, resolves to an address the
    egress guard must never connect to. Always carries code EGRESS_DENIED."""

    def __init__(self, message: str, **context: Any) -> None:
        super().__init__(ErrorCode.EGRESS_DENIED, message, **context)


class VerificationIOError(StructuredError):
    """Raised when a `verify_ownership()` method suffers a hard I/O failure
    (DNS lookup error, connection reset) — distinct from a normal
    `VerificationResult(verified=False)`, which means "checked, not present
    yet," not "couldn't check." Always carries code VERIFICATION_IO_FAILED."""

    def __init__(self, message: str, **context: Any) -> None:
        super().__init__(ErrorCode.VERIFICATION_IO_FAILED, message, **context)
