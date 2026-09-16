from __future__ import annotations

from vigilo_core.errors import ErrorCode
from vigilo_core.models import Tier
from vigilo_security.authorization import AuthorizationRequest, resolve_authorization


def _request(**overrides) -> AuthorizationRequest:
    defaults = dict(
        target_origin="https://example.com",
        requested_tier=Tier.PASSIVE,
        target_verification_status=Tier.PASSIVE,
        target_opt_out=False,
        ownership_proof_valid=False,
        recent_scan_count_24h=0,
        denylisted=False,
    )
    defaults.update(overrides)
    return AuthorizationRequest(**defaults)


def test_a_denylisted_target_is_denied_outright():
    decision = resolve_authorization(_request(denylisted=True, requested_tier=Tier.PASSIVE))
    assert decision.allowed is False
    assert decision.granted_tier == Tier.PASSIVE
    assert decision.denial_code == ErrorCode.TARGET_OPTED_OUT


def test_an_opted_out_target_is_denied_outright():
    decision = resolve_authorization(_request(target_opt_out=True))
    assert decision.allowed is False
    assert decision.denial_code == ErrorCode.TARGET_OPTED_OUT


def test_over_the_rate_ceiling_is_denied():
    decision = resolve_authorization(_request(recent_scan_count_24h=999))
    assert decision.allowed is False
    assert decision.denial_code == ErrorCode.RATE_LIMIT_EXCEEDED


def test_a_plain_passive_request_is_allowed_at_passive():
    decision = resolve_authorization(_request())
    assert decision.allowed is True
    assert decision.granted_tier == Tier.PASSIVE


def test_active_request_without_a_valid_proof_downgrades_to_passive_not_a_rejection():
    decision = resolve_authorization(
        _request(
            requested_tier=Tier.ACTIVE,
            target_verification_status=Tier.PASSIVE,
            ownership_proof_valid=False,
        )
    )
    assert decision.allowed is True
    assert decision.granted_tier == Tier.PASSIVE
    assert decision.denial_code == ErrorCode.TIER_NOT_PERMITTED


def test_active_request_with_verified_status_but_expired_proof_still_downgrades():
    decision = resolve_authorization(
        _request(
            requested_tier=Tier.ACTIVE,
            target_verification_status=Tier.ACTIVE,
            ownership_proof_valid=False,
        )
    )
    assert decision.allowed is True
    assert decision.granted_tier == Tier.PASSIVE


def test_active_request_with_a_valid_proof_is_granted_active():
    decision = resolve_authorization(
        _request(
            requested_tier=Tier.ACTIVE,
            target_verification_status=Tier.ACTIVE,
            ownership_proof_valid=True,
        )
    )
    assert decision.allowed is True
    assert decision.granted_tier == Tier.ACTIVE
    assert decision.denial_code is None


def test_active_request_with_a_valid_proof_but_plan_disallows_active_downgrades_to_passive():
    decision = resolve_authorization(
        _request(
            requested_tier=Tier.ACTIVE,
            target_verification_status=Tier.ACTIVE,
            ownership_proof_valid=True,
            active_tier_permitted_by_plan=False,
        )
    )
    assert decision.allowed is True
    assert decision.granted_tier == Tier.PASSIVE
    assert decision.denial_code == ErrorCode.TIER_NOT_PERMITTED


def test_active_tier_permitted_by_plan_defaults_to_true_when_unset():
    decision = resolve_authorization(
        _request(
            requested_tier=Tier.ACTIVE,
            target_verification_status=Tier.ACTIVE,
            ownership_proof_valid=True,
        )
    )
    assert decision.granted_tier == Tier.ACTIVE


def test_denylist_takes_priority_over_a_valid_active_proof():
    decision = resolve_authorization(
        _request(
            denylisted=True,
            requested_tier=Tier.ACTIVE,
            target_verification_status=Tier.ACTIVE,
            ownership_proof_valid=True,
        )
    )
    assert decision.allowed is False
    assert decision.granted_tier == Tier.PASSIVE
