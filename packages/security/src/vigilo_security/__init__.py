"""Vigilo security: everything that decides whether an action against a third
party is permitted (docs/modules.md §2).

Phase 0 shipped the egress guard (SSRF/DNS-rebinding defense). Phase 3 adds
scan authorization (`resolve_authorization`), ownership verification
(`verify_ownership`) and the append-only audit trail writer (`audit`) —
these need `Account`/`Target` persistence, which is why they were deferred
until now (docs/build-roadmap.md). This is the deliberate, documented point
where `security` gains a dependency on `vigilo-persistence` beyond `core`.
"""

from vigilo_security.audit import AuditEvent, audit
from vigilo_security.authorization import (
    AuthorizationDecision,
    AuthorizationRequest,
    resolve_authorization,
)
from vigilo_security.egress_guard import (
    DeniedReason,
    ValidatedConnection,
    revalidate_redirect,
    validate_and_pin,
)
from vigilo_security.exceptions import EgressDenied, VerificationIOError
from vigilo_security.ownership import (
    VerificationResult,
    verify_dns_txt,
    verify_email,
    verify_meta_tag,
    verify_ownership,
    verify_wellknown_file,
)

__all__ = [
    "DeniedReason",
    "ValidatedConnection",
    "revalidate_redirect",
    "validate_and_pin",
    "EgressDenied",
    "VerificationIOError",
    "AuthorizationRequest",
    "AuthorizationDecision",
    "resolve_authorization",
    "VerificationResult",
    "verify_ownership",
    "verify_dns_txt",
    "verify_wellknown_file",
    "verify_meta_tag",
    "verify_email",
    "AuditEvent",
    "audit",
]
