from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest_asyncio

from vigilo_api.deps import require_account
from vigilo_api.main import app
from vigilo_identity.repository import (
    get_account_by_id,
    get_or_create_account,
    upsert_subscription,
)
from vigilo_persistence import session_scope


async def _upgrade_to_builder(account_id, email: str):
    async with session_scope() as session:
        await upsert_subscription(
            session,
            account_id=account_id,
            plan_id="builder",
            status="active",
            provider="paddle",
            provider_subscription_id=f"sub_{email}",
            current_period_end=None,
        )
        return await get_account_by_id(session, account_id)


@pytest_asyncio.fixture
async def builder_account():
    async with session_scope() as session:
        acc = await get_or_create_account(
            session, email="monitor-owner@example.com", clerk_user_id="user_monitor"
        )
    acc = await _upgrade_to_builder(acc.id, acc.email)
    app.dependency_overrides[require_account] = lambda: acc
    yield acc
    app.dependency_overrides.pop(require_account, None)


@pytest_asyncio.fixture
async def free_account():
    async with session_scope() as session:
        acc = await get_or_create_account(
            session, email="free-monitor@example.com", clerk_user_id="user_free_monitor"
        )
    app.dependency_overrides[require_account] = lambda: acc
    yield acc
    app.dependency_overrides.pop(require_account, None)


async def test_create_monitor_on_the_free_plan_is_denied(client, free_account):
    create_target = await client.post("/v1/targets", json={"origin": "https://example.com"})
    target_id = create_target.json()["target_id"]

    response = await client.post(
        f"/v1/targets/{target_id}/monitors", json={"cadence_hours": 168}
    )

    assert response.status_code == 429
    assert response.json()["code"] == "QUOTA_EXCEEDED"


async def test_create_monitor_on_builder_with_the_correct_weekly_cadence(client, builder_account):
    create_target = await client.post("/v1/targets", json={"origin": "https://example.com"})
    target_id = create_target.json()["target_id"]

    response = await client.post(
        f"/v1/targets/{target_id}/monitors", json={"cadence_hours": 168}
    )

    assert response.status_code == 201
    body = response.json()
    assert body["target_id"] == target_id
    assert body["cadence_hours"] == 168
    assert body["enabled"] is True


async def test_create_monitor_on_builder_with_a_non_weekly_cadence_is_rejected(
    client, builder_account
):
    create_target = await client.post("/v1/targets", json={"origin": "https://example.com"})
    target_id = create_target.json()["target_id"]

    response = await client.post(f"/v1/targets/{target_id}/monitors", json={"cadence_hours": 24})

    assert response.status_code == 422


async def test_creating_a_monitor_twice_for_the_same_target_updates_not_duplicates(
    client, builder_account
):
    create_target = await client.post("/v1/targets", json={"origin": "https://example.com"})
    target_id = create_target.json()["target_id"]

    first = await client.post(f"/v1/targets/{target_id}/monitors", json={"cadence_hours": 168})
    second = await client.post(
        f"/v1/targets/{target_id}/monitors",
        json={"cadence_hours": 168, "quiet_start_utc": 22, "quiet_end_utc": 7},
    )

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["monitor_id"] == second.json()["monitor_id"]
    assert second.json()["quiet_start_utc"] == 22


async def test_create_monitor_beyond_the_builder_plan_limit_is_denied(client, builder_account):
    """Builder's `monitors_limit` (3) equals its `targets_limit` (3), so
    the normal one-target-then-one-monitor HTTP flow always hits the
    TARGETS quota first on a 4th target — it can never actually reach the
    MONITORS quota through that path. To isolate the MONITORS check
    itself, the first 3 targets+monitors are seeded directly via the
    repository (bypassing `POST /v1/targets`' own TARGETS quota, exactly
    as Phase 6/7 established for reaching states the normal flow can't),
    and only the 4th, denied monitor-creation call goes through the real
    HTTP endpoint under test."""
    from vigilo_monitoring.repository import create_monitor as create_monitor_row
    from vigilo_project.repository import create_target, get_or_create_default_project

    async with session_scope() as session:
        project = await get_or_create_default_project(session, builder_account.id)
        for i in range(3):
            target = await create_target(session, project.id, f"https://seed{i}.example.com")
            await create_monitor_row(
                session,
                target_id=target.id,
                account_id=builder_account.id,
                cadence_hours=168,
                next_run_at=datetime.now(UTC),
            )
        over_target = await create_target(session, project.id, "https://over.example.com")

    response = await client.post(
        f"/v1/targets/{over_target.id}/monitors", json={"cadence_hours": 168}
    )

    assert response.status_code == 429
    assert response.json()["code"] == "QUOTA_EXCEEDED"


async def test_get_target_monitor_returns_404_when_none_exists(client, builder_account):
    create_target = await client.post("/v1/targets", json={"origin": "https://example.com"})
    target_id = create_target.json()["target_id"]

    response = await client.get(f"/v1/targets/{target_id}/monitors")

    assert response.status_code == 404


async def test_disable_monitor_requires_ownership(client, builder_account):
    create_target = await client.post("/v1/targets", json={"origin": "https://example.com"})
    target_id = create_target.json()["target_id"]
    create_response = await client.post(
        f"/v1/targets/{target_id}/monitors", json={"cadence_hours": 168}
    )
    monitor_id = create_response.json()["monitor_id"]

    async with session_scope() as session:
        other = await get_or_create_account(
            session, email="other-monitor@example.com", clerk_user_id="user_other_monitor"
        )
    app.dependency_overrides[require_account] = lambda: other

    response = await client.post(f"/v1/monitors/{monitor_id}/disable")
    assert response.status_code == 404


async def test_disable_monitor_succeeds_for_the_owner(client, builder_account):
    create_target = await client.post("/v1/targets", json={"origin": "https://example.com"})
    target_id = create_target.json()["target_id"]
    create_response = await client.post(
        f"/v1/targets/{target_id}/monitors", json={"cadence_hours": 168}
    )
    monitor_id = create_response.json()["monitor_id"]

    response = await client.post(f"/v1/monitors/{monitor_id}/disable")

    assert response.status_code == 200
    assert response.json()["enabled"] is False


async def test_disable_an_unknown_monitor_returns_404(client, builder_account):
    response = await client.post(f"/v1/monitors/{uuid.uuid4()}/disable")
    assert response.status_code == 404


async def test_score_history_returns_scans_for_the_target(client, builder_account):
    create_target = await client.post("/v1/targets", json={"origin": "https://example.com"})
    target_id = create_target.json()["target_id"]

    response = await client.get(f"/v1/targets/{target_id}/scores")

    assert response.status_code == 200
    assert response.json() == []


async def test_alerts_list_starts_empty_for_a_new_target(client, builder_account):
    create_target = await client.post("/v1/targets", json={"origin": "https://example.com"})
    target_id = create_target.json()["target_id"]

    response = await client.get(f"/v1/targets/{target_id}/alerts")

    assert response.status_code == 200
    assert response.json() == []


async def test_target_monitor_endpoints_require_authentication(client):
    response = await client.post(
        f"/v1/targets/{uuid.uuid4()}/monitors", json={"cadence_hours": 168}
    )
    assert response.status_code == 401
