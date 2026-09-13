from __future__ import annotations

import uuid

import vigilo_api.routers.scans as scans_module


async def test_submit_scan_returns_202_with_the_authorized_status(client):
    response = await client.post(
        "/v1/scans", json={"target_url": "https://example.com", "email": "owner@example.com"}
    )

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "authorized"
    assert body["granted_tier"] == "passive"
    assert "scan_job_id" in body


async def test_submit_scan_rejects_a_malformed_url(client):
    response = await client.post(
        "/v1/scans", json={"target_url": "not-a-url", "email": "owner@example.com"}
    )
    assert response.status_code == 422


async def test_submit_scan_rejects_an_invalid_email(client):
    response = await client.post(
        "/v1/scans", json={"target_url": "https://example.com", "email": "not-an-email"}
    )
    assert response.status_code == 422


async def test_submit_scan_denies_a_denylisted_target(client, monkeypatch):
    monkeypatch.setattr(scans_module, "_DENYLIST", frozenset({"https://denylisted.test"}))

    response = await client.post(
        "/v1/scans", json={"target_url": "https://denylisted.test", "email": "owner@example.com"}
    )
    assert response.status_code == 403


async def test_get_scan_status_returns_404_for_an_unknown_job(client):
    response = await client.get(f"/v1/scans/{uuid.uuid4()}")
    assert response.status_code == 404


async def test_get_scan_status_reflects_the_authorized_job(client):
    submit_response = await client.post(
        "/v1/scans", json={"target_url": "https://example.com", "email": "owner@example.com"}
    )
    job_id = submit_response.json()["scan_job_id"]

    response = await client.get(f"/v1/scans/{job_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "authorized"
    assert body["target_origin"] == "https://example.com"
    assert body["score"] is None
