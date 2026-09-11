"""Vigilo security: everything that decides whether an action against a third
party is permitted (docs/modules.md §2).

Phase 0 ships only the egress guard (SSRF/DNS-rebinding defense) — the
highest-severity control and the doc's own Phase 0 exit test. Scan
authorization (`resolve_authorization`, `verify_ownership`), the rate
governor and the audit trail writer need `Account`/`Target` persistence and
are built in Phase 3, per docs/build-roadmap.md.
"""

from vigilo_security.egress_guard import (
    DeniedReason,
    ValidatedConnection,
    revalidate_redirect,
    validate_and_pin,
)
from vigilo_security.exceptions import EgressDenied

__all__ = [
    "DeniedReason",
    "ValidatedConnection",
    "revalidate_redirect",
    "validate_and_pin",
    "EgressDenied",
]
