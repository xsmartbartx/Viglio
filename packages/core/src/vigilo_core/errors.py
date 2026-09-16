"""Structured error taxonomy. See docs/modules.md §1 and
docs/prooflight-vision-and-architecture.md §16.3 for the product-specific codes.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any


class ErrorCode(StrEnum):
    """Stable, machine-readable error identifiers.

    Generic codes cover cross-cutting failures; product codes are specific to
    scan authorization and the target lifecycle and are added here as each
    owning module (project, security, orchestrator, billing) is built, so the
    taxonomy stays centralized in Core rather than scattered per module.
    """

    # Generic
    VALIDATION_ERROR = "VALIDATION_ERROR"
    NOT_FOUND = "NOT_FOUND"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    CONFIGURATION_ERROR = "CONFIGURATION_ERROR"

    # Target / scan authorization (docs/prooflight-vision-and-architecture.md §16.3)
    TARGET_INVALID = "TARGET_INVALID"
    TARGET_UNVERIFIED = "TARGET_UNVERIFIED"
    TARGET_OPTED_OUT = "TARGET_OPTED_OUT"
    TIER_NOT_PERMITTED = "TIER_NOT_PERMITTED"
    QUOTA_EXCEEDED = "QUOTA_EXCEEDED"
    EGRESS_DENIED = "EGRESS_DENIED"
    BUDGET_EXHAUSTED = "BUDGET_EXHAUSTED"
    REGISTRY_VERSION_UNKNOWN = "REGISTRY_VERSION_UNKNOWN"

    # Scan authorization / ownership verification (Phase 3, docs/adr/ADR-0003)
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    OWNERSHIP_PROOF_EXPIRED = "OWNERSHIP_PROOF_EXPIRED"
    OWNERSHIP_PROOF_NOT_FOUND = "OWNERSHIP_PROOF_NOT_FOUND"
    VERIFICATION_IO_FAILED = "VERIFICATION_IO_FAILED"

    # Scan orchestrator (Phase 3, docs/modules.md §8)
    INVALID_STATE_TRANSITION = "INVALID_STATE_TRANSITION"
    SCAN_JOB_NOT_FOUND = "SCAN_JOB_NOT_FOUND"

    # Integrations (Phase 3, docs/modules.md §7)
    MAIL_DELIVERY_FAILED = "MAIL_DELIVERY_FAILED"
    OBJECT_STORE_ERROR = "OBJECT_STORE_ERROR"

    # Reporting (Phase 4, docs/modules.md §6)
    REPORT_NOT_FOUND = "REPORT_NOT_FOUND"
    REPORT_NOT_READY = "REPORT_NOT_READY"
    SHARE_LINK_NOT_FOUND = "SHARE_LINK_NOT_FOUND"
    SHARE_LINK_EXPIRED = "SHARE_LINK_EXPIRED"
    SHARE_LINK_REVOKED = "SHARE_LINK_REVOKED"
    PDF_RENDER_FAILED = "PDF_RENDER_FAILED"

    # Integrations (Phase 5, docs/modules.md §7)
    LLM_PROVIDER_ERROR = "LLM_PROVIDER_ERROR"

    # Integrations (Phase 7, docs/modules.md §7)
    BILLING_PROVIDER_ERROR = "BILLING_PROVIDER_ERROR"


class StructuredError(Exception):
    """A structured, loggable error carrying a stable code and sanitized context.

    `context` must never contain secret values or raw evidence — callers pass
    only already-safe data (ids, enum values, counts). This is enforced by
    convention at each call site, not by this class, matching the ownership
    model in docs/modules.md (Core provides the shape; callers are responsible
    for what they put in it).
    """

    def __init__(self, code: ErrorCode, message: str, **context: Any) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.context = context

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code.value, "message": self.message, "context": self.context}

    def __repr__(self) -> str:
        return f"StructuredError(code={self.code.value!r}, message={self.message!r})"


def error(code: ErrorCode, message: str, **context: Any) -> StructuredError:
    """Build a StructuredError. Does not raise — the caller decides whether to
    raise it, log it, or attach it to a result object."""
    return StructuredError(code, message, **context)
