from __future__ import annotations

from vigilo_billing.entitlements import entitlements
from vigilo_billing.models import PlanId


def test_free_plan_entitlements():
    result = entitlements("free")
    assert result.plan_id == PlanId.FREE
    assert result.targets_limit == 1
    assert result.scans_per_month_limit == 3
    assert result.active_tier_allowed is False
    assert result.share_links_allowed is False
    assert result.monitoring_frequency is None
    assert result.monitors_limit == 0
    assert result.api_keys_limit == 0
    assert result.white_label_allowed is False


def test_builder_plan_entitlements():
    result = entitlements("builder")
    assert result.plan_id == PlanId.BUILDER
    assert result.targets_limit == 3
    assert result.scans_per_month_limit == 100
    assert result.active_tier_allowed is True
    assert result.share_links_allowed is True
    assert result.monitoring_frequency == "weekly"
    assert result.monitors_limit == 3
    assert result.api_keys_limit == 1
    assert result.api_rate_limit_per_minute == 60
    assert result.white_label_allowed is False


def test_studio_plan_has_unlimited_scans():
    result = entitlements("studio")
    assert result.plan_id == PlanId.STUDIO
    assert result.targets_limit == 25
    assert result.scans_per_month_limit is None
    assert result.monitoring_frequency == "daily+custom"
    assert result.monitors_limit == 25
    assert result.white_label_allowed is False


def test_business_plan_is_the_only_plan_with_white_label_allowed():
    result = entitlements("business")
    assert result.plan_id == PlanId.BUSINESS
    assert result.targets_limit == 100
    assert result.scans_per_month_limit is None
    assert result.white_label_allowed is True
    assert result.api_keys_limit == 100
    assert result.api_rate_limit_per_minute == 1000

    for plan_id in ("free", "builder", "studio"):
        assert entitlements(plan_id).white_label_allowed is False


def test_none_plan_id_defaults_to_free():
    assert entitlements(None).plan_id == PlanId.FREE


def test_unrecognized_plan_id_defaults_to_free():
    """Fail closed: an unrecognized plan_id (a typo, a stale/removed plan)
    must never fail open into an unrestricted plan."""
    assert entitlements("not-a-real-plan").plan_id == PlanId.FREE
