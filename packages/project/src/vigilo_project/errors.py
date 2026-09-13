"""Domain-specific exceptions for `project`, one-line subclasses of
`StructuredError` hardcoding their `ErrorCode` — the same pattern
`vigilo_security.exceptions.EgressDenied` established.
"""

from __future__ import annotations

from typing import Any

from vigilo_core.errors import ErrorCode, StructuredError


class OwnershipProofNotFound(StructuredError):
    def __init__(self, message: str, **context: Any) -> None:
        super().__init__(ErrorCode.OWNERSHIP_PROOF_NOT_FOUND, message, **context)


class OwnershipProofExpired(StructuredError):
    def __init__(self, message: str, **context: Any) -> None:
        super().__init__(ErrorCode.OWNERSHIP_PROOF_EXPIRED, message, **context)
