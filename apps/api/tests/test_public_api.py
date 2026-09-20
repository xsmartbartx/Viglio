from __future__ import annotations

from redis.asyncio import Redis

from vigilo_api.routers.public_api import scan_status_events
from vigilo_core.config import config
from vigilo_core.models import Confidence, Finding, Score, Severity, Tier, Verdict
from vigilo_identity.repository import (
    create_api_key,
    get_account_by_id,
    get_or_create_account,
    list_api_keys_for_account,
    revoke_api_key,
    upsert_subscription,
)
from vigilo_orchestrator.service import advance, create_scan_job, record_scan_result
from vigilo_persistence import session_scope
from vigilo_project.repository import create_target, get_or_create_default_project


async def _create_account_and_key(email: str, plan_id: str, scopes: list[str]):
    async with session_scope() as session:
        account = await get_or_create_account(session, email=email)
        if plan_id != "free":
            await upsert_subscription(
                session,
                account_id=account.id,
                plan_id=plan_id,
                status="active",
                provider="paddle",
                provider_subscription_id=f"sub_{email}",
                current_period_end=None,
            )
            account = await get_account_by_id(session, account.id)
        _api_key, raw_key = await create_api_key(session, account.id, "test key", scopes)
    return account, raw_key


def _auth(raw_key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {raw_key}"}


async def test_public_api_requires_a_bearer_token(client):
    response = await client.get("/public/v1/projects")
    assert response.status_code == 401


async def test_public_api_rejects_an_unknown_key(client):
    response = await client.get("/public/v1/projects", headers=_auth("vglo_not-a-real-key"))
    assert response.status_code == 401


async def test_public_api_rejects_a_revoked_key(client):
    account, raw_key = await _create_account_and_key(
        "revoked-key@example.com", "builder", ["project:read"]
    )
    async with session_scope() as session:
        keys = await list_api_keys_for_account(session, account.id)
        await revoke_api_key(session, keys[0].id)

    response = await client.get("/public/v1/projects", headers=_auth(raw_key))
    assert response.status_code == 401


async def test_public_api_denies_a_key_missing_the_required_scope(client):
    _account, raw_key = await _create_account_and_key(
        "wrong-scope@example.com", "builder", ["project:read"]
    )

    response = await client.post(
        "/public/v1/scans",
        json={"target_url": "https://example.com"},
        headers=_auth(raw_key),
    )

    assert response.status_code == 403


async def test_public_submit_scan_creates_a_real_scan_job(client):
    _account, raw_key = await _create_account_and_key(
        "public-scan@example.com", "builder", ["scan:run"]
    )

    response = await client.post(
        "/public/v1/scans",
        json={"target_url": "https://example.com"},
        headers=_auth(raw_key),
    )

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "authorized"
    assert body["granted_tier"] == "passive"


async def test_public_get_scan_status_denies_access_to_another_accounts_scan(client):
    _owner, owner_key = await _create_account_and_key(
        "scan-owner@example.com", "builder", ["scan:run", "scan:read"]
    )
    create_response = await client.post(
        "/public/v1/scans",
        json={"target_url": "https://example.com"},
        headers=_auth(owner_key),
    )
    scan_job_id = create_response.json()["scan_job_id"]

    _other, other_key = await _create_account_and_key(
        "scan-intruder@example.com", "builder", ["scan:read"]
    )

    response = await client.get(f"/public/v1/scans/{scan_job_id}", headers=_auth(other_key))
    assert response.status_code == 404


async def test_public_get_scan_status_succeeds_for_the_owner(client):
    _account, raw_key = await _create_account_and_key(
        "scan-status@example.com", "builder", ["scan:run", "scan:read"]
    )
    create_response = await client.post(
        "/public/v1/scans",
        json={"target_url": "https://example.com"},
        headers=_auth(raw_key),
    )
    scan_job_id = create_response.json()["scan_job_id"]

    response = await client.get(f"/public/v1/scans/{scan_job_id}", headers=_auth(raw_key))

    assert response.status_code == 200
    assert response.json()["scan_job_id"] == scan_job_id


async def test_public_get_scan_report_and_findings(client):
    account, raw_key = await _create_account_and_key(
        "public-report@example.com", "builder", ["report:read"]
    )
    async with session_scope() as session:
        project = await get_or_create_default_project(session, account.id)
        target = await create_target(session, project.id, "https://example.com")
        job = await create_scan_job(session, target.id, Tier.PASSIVE, account.email, "0.1")
        job = await advance(session, job.id, "authorized")
        job = await advance(session, job.id, "probing")
        job = await advance(session, job.id, "evaluating")
        job = await advance(session, job.id, "scoring")
        findings = [
            Finding(
                check_id="VG-HDR-001",
                verdict=Verdict.FAILED,
                severity=Severity.HIGH,
                confidence=Confidence.CONFIRMED,
                title="HSTS enforced",
                summary="No HSTS header present.",
                fingerprint="fp1",
            )
        ]
        score = Score(value=83.0, grade="B", registry_version="0.1")
        await record_scan_result(session, job, findings, score, duration_ms=10)

    report_response = await client.get(
        f"/public/v1/scans/{job.id}/report", headers=_auth(raw_key)
    )
    assert report_response.status_code == 200
    assert report_response.json()["score"] == 83.0

    findings_response = await client.get(
        f"/public/v1/scans/{job.id}/findings", headers=_auth(raw_key)
    )
    assert findings_response.status_code == 200
    assert len(findings_response.json()) == 1

    sarif_response = await client.get(
        f"/public/v1/scans/{job.id}/report.sarif", headers=_auth(raw_key)
    )
    assert sarif_response.status_code == 200
    assert sarif_response.headers["content-type"] == "application/sarif+json"
    sarif = sarif_response.json()
    assert sarif["version"] == "2.1.0"
    assert sarif["runs"][0]["results"][0]["ruleId"] == "VG-HDR-001"


async def test_public_get_scan_report_sarif_requires_ownership(client):
    account, _raw_key = await _create_account_and_key(
        "public-sarif-owner@example.com", "builder", ["report:read"]
    )
    _other_account, other_raw_key = await _create_account_and_key(
        "public-sarif-other@example.com", "builder", ["report:read"]
    )
    async with session_scope() as session:
        project = await get_or_create_default_project(session, account.id)
        target = await create_target(session, project.id, "https://example.com")
        job = await create_scan_job(session, target.id, Tier.PASSIVE, account.email, "0.1")

    response = await client.get(
        f"/public/v1/scans/{job.id}/report.sarif", headers=_auth(other_raw_key)
    )
    assert response.status_code == 404


async def test_public_score_history_and_projects(client):
    account, raw_key = await _create_account_and_key(
        "public-scores@example.com", "builder", ["report:read", "project:read"]
    )
    async with session_scope() as session:
        project = await get_or_create_default_project(session, account.id)
        target = await create_target(session, project.id, "https://example.com")

    scores_response = await client.get(
        f"/public/v1/targets/{target.id}/scores", headers=_auth(raw_key)
    )
    assert scores_response.status_code == 200
    assert scores_response.json() == []

    projects_response = await client.get("/public/v1/projects", headers=_auth(raw_key))
    assert projects_response.status_code == 200
    assert len(projects_response.json()) == 1
    assert projects_response.json()[0]["project_id"] == str(project.id)


async def test_public_monitor_lifecycle(client):
    account, raw_key = await _create_account_and_key(
        "public-monitor@example.com", "builder", ["monitor:write", "monitor:read"]
    )
    async with session_scope() as session:
        project = await get_or_create_default_project(session, account.id)
        target = await create_target(session, project.id, "https://example.com")

    create_response = await client.post(
        f"/public/v1/targets/{target.id}/monitors",
        json={"cadence_hours": 168},
        headers=_auth(raw_key),
    )
    assert create_response.status_code == 201
    monitor_id = create_response.json()["monitor_id"]

    get_response = await client.get(
        f"/public/v1/targets/{target.id}/monitors", headers=_auth(raw_key)
    )
    assert get_response.status_code == 200
    assert get_response.json()["monitor_id"] == monitor_id

    disable_response = await client.post(
        f"/public/v1/monitors/{monitor_id}/disable", headers=_auth(raw_key)
    )
    assert disable_response.status_code == 200
    assert disable_response.json()["enabled"] is False


async def test_public_api_rate_limit_returns_429_with_retry_after(client):
    account, raw_key = await _create_account_and_key(
        "public-ratelimit@example.com", "builder", ["project:read"]
    )
    # Builder's api_rate_limit_per_minute is 60 — pre-load the counter past
    # the limit directly in Redis rather than making 60 real requests.
    redis = Redis.from_url(config().redis_url)
    try:
        await redis.set(f"ratelimit:{account.id}", 60, ex=60)

        response = await client.get("/public/v1/projects", headers=_auth(raw_key))

        assert response.status_code == 429
        assert "Retry-After" in response.headers
    finally:
        await redis.delete(f"ratelimit:{account.id}")
        await redis.aclose()


async def test_scan_status_events_yields_on_every_status_change(client):
    """Unit-tests `scan_status_events()` directly rather than through the
    full HTTP/ASGI stack — httpx's `ASGITransport` buffers a streaming
    response until the generator itself finishes, so a real request
    through `client` can't observe incremental yields without waiting out
    `max_seconds` regardless of how quickly they actually happen. `client`
    is unused directly but its fixture is what provisions the schema this
    test writes to."""
    account, raw_key = await _create_account_and_key(
        "public-stream@example.com", "builder", ["scan:run"]
    )
    async with session_scope() as session:
        project = await get_or_create_default_project(session, account.id)
        target = await create_target(session, project.id, "https://example.com")
        job = await create_scan_job(session, target.id, Tier.PASSIVE, account.email, "0.1")
        job = await advance(session, job.id, "authorized")

        events = [
            line async for line in scan_status_events(session, job.id, 0.01, 0.05)
        ]

    assert len(events) >= 1
    assert '"status": "authorized"' in events[0]


async def test_public_scan_stream_endpoint_returns_the_right_content_type(client, monkeypatch):
    import vigilo_api.routers.public_api as public_api_module

    monkeypatch.setattr(public_api_module, "_STREAM_MAX_SECONDS", 0.05)
    monkeypatch.setattr(public_api_module, "_STREAM_POLL_SECONDS", 0.01)

    _account, raw_key = await _create_account_and_key(
        "public-stream-http@example.com", "builder", ["scan:run", "scan:read"]
    )
    create_response = await client.post(
        "/public/v1/scans",
        json={"target_url": "https://example.com"},
        headers=_auth(raw_key),
    )
    scan_job_id = create_response.json()["scan_job_id"]

    response = await client.get(
        f"/public/v1/scans/{scan_job_id}/stream", headers=_auth(raw_key)
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "authorized" in response.text
