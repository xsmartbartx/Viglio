from __future__ import annotations

from typing import Any

from vigilo_core.errors import ErrorCode, StructuredError


class ScanJobNotFound(StructuredError):
    def __init__(self, message: str, **context: Any) -> None:
        super().__init__(ErrorCode.SCAN_JOB_NOT_FOUND, message, **context)


class InvalidScanTransition(StructuredError):
    def __init__(self, message: str, **context: Any) -> None:
        super().__init__(ErrorCode.INVALID_STATE_TRANSITION, message, **context)


class ReportNotFound(StructuredError):
    def __init__(self, message: str, **context: Any) -> None:
        super().__init__(ErrorCode.REPORT_NOT_FOUND, message, **context)


class ShareLinkNotFound(StructuredError):
    def __init__(self, message: str, **context: Any) -> None:
        super().__init__(ErrorCode.SHARE_LINK_NOT_FOUND, message, **context)
