"""Maps `StructuredError` to an HTTP response — the gap the Phase 0 bootstrap
left open (an uncaught `StructuredError` surfaced as an unhandled 500 with a
stack trace). Registered once in `main.py` as a catch-all; individual
handlers still raise `HTTPException` directly where a more specific status
is clearer at the call site.
"""

from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse

from vigilo_core.errors import ErrorCode, StructuredError

_STATUS_BY_CODE: dict[ErrorCode, int] = {
    ErrorCode.NOT_FOUND: 404,
    ErrorCode.SCAN_JOB_NOT_FOUND: 404,
    ErrorCode.OWNERSHIP_PROOF_NOT_FOUND: 404,
    ErrorCode.VALIDATION_ERROR: 422,
    ErrorCode.TARGET_INVALID: 422,
    ErrorCode.TARGET_UNVERIFIED: 403,
    ErrorCode.TARGET_OPTED_OUT: 403,
    ErrorCode.TIER_NOT_PERMITTED: 403,
    ErrorCode.RATE_LIMIT_EXCEEDED: 429,
    ErrorCode.QUOTA_EXCEEDED: 429,
    ErrorCode.OWNERSHIP_PROOF_EXPIRED: 410,
    ErrorCode.INVALID_STATE_TRANSITION: 409,
    ErrorCode.REPORT_NOT_FOUND: 404,
    ErrorCode.REPORT_NOT_READY: 409,
    ErrorCode.SHARE_LINK_NOT_FOUND: 404,
    ErrorCode.SHARE_LINK_EXPIRED: 410,
    ErrorCode.SHARE_LINK_REVOKED: 410,
    ErrorCode.PDF_RENDER_FAILED: 500,
}


async def handle_structured_error(request: Request, exc: StructuredError) -> JSONResponse:
    status_code = _STATUS_BY_CODE.get(exc.code, 500)
    return JSONResponse(status_code=status_code, content=exc.to_dict())
