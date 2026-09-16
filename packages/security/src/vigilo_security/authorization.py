"""resolve_authorization(): tier resolution (docs/modules.md §2, ADR-0003).

A pure function over primitives/enums only — no ORM types — matching
`security`'s dependency-graph position (depends on `core` only; it must not
import `vigilo_identity`/`vigilo_project`). The caller (an `apps/api` request
handler) loads whatever `Account`/`Target`/`OwnershipProof` state it needs
and reduces it to this function's inputs before calling it.

Fail-closed per ADR-0003: any error, unrecognized state, or an active
request without a valid proof downgrades to `passive`, or denies outright
for denylist/opt-out/rate-limit — it never upgrades.
"""

from __future__ import annotations

from dataclasses import dataclass

from vigilo_core.errors import ErrorCode
from vigilo_core.models import Tier

_RECENT_SCAN_CEILING = 20
"""Minimal, DB-derived abuse ceiling per docs/build-roadmap.md's Phase 3
scope trim — a fixed constant, not the full Redis-backed rate governor
(`check_rate()`), which is Phase 6/7 per docs/security.md's tracking table."""


@dataclass(frozen=True)
class AuthorizationRequest:
    target_origin: str
    requested_tier: Tier
    target_verification_status: Tier
    target_opt_out: bool
    ownership_proof_valid: bool
    recent_scan_count_24h: int
    denylisted: bool
    active_tier_permitted_by_plan: bool = True
    """Whether the submitter's plan includes active tier at all (Phase 7,
    packages/billing). Defaulted True so a caller that hasn't been updated
    to compute this (or a brand-new submitter with no account/plan yet)
    is unaffected — the existing ownership-proof gate independently blocks
    active tier for anyone without a verified target regardless."""


@dataclass(frozen=True)
class AuthorizationDecision:
    allowed: bool
    granted_tier: Tier
    reason: str
    denial_code: ErrorCode | None = None


def resolve_authorization(request: AuthorizationRequest) -> AuthorizationDecision:
    if request.denylisted:
        return AuthorizationDecision(
            allowed=False,
            granted_tier=Tier.PASSIVE,
            reason="target is on the denylist",
            denial_code=ErrorCode.TARGET_OPTED_OUT,
        )

    if request.target_opt_out:
        return AuthorizationDecision(
            allowed=False,
            granted_tier=Tier.PASSIVE,
            reason="target owner has opted out",
            denial_code=ErrorCode.TARGET_OPTED_OUT,
        )

    if request.recent_scan_count_24h > _RECENT_SCAN_CEILING:
        return AuthorizationDecision(
            allowed=False,
            granted_tier=Tier.PASSIVE,
            reason="rate limit exceeded for this target",
            denial_code=ErrorCode.RATE_LIMIT_EXCEEDED,
        )

    if request.requested_tier == Tier.ACTIVE:
        has_active_verification = (
            request.target_verification_status == Tier.ACTIVE and request.ownership_proof_valid
        )
        if not has_active_verification:
            # A downgrade, not a failure — ADR-0003: "never upgrades," which
            # implies a request for more than is available is granted at
            # what IS available, not rejected outright.
            return AuthorizationDecision(
                allowed=True,
                granted_tier=Tier.PASSIVE,
                reason="active tier requested without a valid, unexpired ownership proof",
                denial_code=ErrorCode.TIER_NOT_PERMITTED,
            )
        if not request.active_tier_permitted_by_plan:
            return AuthorizationDecision(
                allowed=True,
                granted_tier=Tier.PASSIVE,
                reason="active tier requested but the account's plan does not include it",
                denial_code=ErrorCode.TIER_NOT_PERMITTED,
            )
        return AuthorizationDecision(
            allowed=True, granted_tier=Tier.ACTIVE, reason="verified owner"
        )

    return AuthorizationDecision(allowed=True, granted_tier=Tier.PASSIVE, reason="passive tier")
