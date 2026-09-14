from __future__ import annotations

from typing import Any

from vigilo_core.errors import ErrorCode, StructuredError


class PdfRenderError(StructuredError):
    def __init__(self, message: str, **context: Any) -> None:
        super().__init__(ErrorCode.PDF_RENDER_FAILED, message, **context)
