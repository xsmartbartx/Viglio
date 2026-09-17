from __future__ import annotations

import pytest

import vigilo_mcp.server as server_module
from vigilo_mcp.client import VigiloApiError
from vigilo_mcp.server import get_findings, get_fix_prompt, run_scan


async def test_run_scan_returns_the_report_once_complete(monkeypatch):
    async def fake_submit_scan(target_url, requested_tier):
        return {"scan_job_id": "job-1", "status": "authorized"}

    async def fake_get_scan_status(scan_job_id):
        return {"status": "complete"}

    async def fake_get_scan_report(scan_job_id):
        return {"score": 92.0, "grade": "A"}

    monkeypatch.setattr(server_module, "submit_scan", fake_submit_scan)
    monkeypatch.setattr(server_module, "get_scan_status", fake_get_scan_status)
    monkeypatch.setattr(server_module, "get_scan_report", fake_get_scan_report)

    result = await run_scan("https://example.com")

    assert result == {"score": 92.0, "grade": "A"}


async def test_run_scan_returns_a_still_running_status_without_a_report(monkeypatch):
    async def fake_submit_scan(target_url, requested_tier):
        return {"scan_job_id": "job-2", "status": "authorized"}

    async def fake_get_scan_status(scan_job_id):
        return {"status": "unreachable"}

    async def should_not_be_called(scan_job_id):
        raise AssertionError(
            "get_scan_report should not be called for a non-complete terminal status"
        )

    monkeypatch.setattr(server_module, "submit_scan", fake_submit_scan)
    monkeypatch.setattr(server_module, "get_scan_status", fake_get_scan_status)
    monkeypatch.setattr(server_module, "get_scan_report", should_not_be_called)

    result = await run_scan("https://example.com")

    assert result == {"scan_job_id": "job-2", "status": "unreachable", "report": None}


async def test_run_scan_times_out_gracefully_if_never_terminal(monkeypatch):
    async def fake_submit_scan(target_url, requested_tier):
        return {"scan_job_id": "job-3", "status": "authorized"}

    async def fake_get_scan_status(scan_job_id):
        return {"status": "probing"}

    monkeypatch.setattr(server_module, "submit_scan", fake_submit_scan)
    monkeypatch.setattr(server_module, "get_scan_status", fake_get_scan_status)
    # Small enough to keep the test fast (a handful of real ~10ms sleeps)
    # without touching asyncio.sleep itself, which is process-global.
    monkeypatch.setattr(server_module, "_MAX_WAIT_SECONDS", 0.05)
    monkeypatch.setattr(server_module, "_POLL_INTERVAL_SECONDS", 0.01)

    result = await run_scan("https://example.com")

    assert result["scan_job_id"] == "job-3"
    assert result["status"] == "still_running"


async def test_get_findings_returns_the_raw_findings_list(monkeypatch):
    async def fake_get_scan_findings(scan_job_id):
        return [{"check_id": "VG-HDR-001"}]

    monkeypatch.setattr(server_module, "get_scan_findings", fake_get_scan_findings)

    result = await get_findings("job-1")

    assert result == [{"check_id": "VG-HDR-001"}]


async def test_get_fix_prompt_finds_the_matching_finding(monkeypatch):
    async def fake_get_scan_findings(scan_job_id):
        return [
            {"check_id": "VG-HDR-001", "remediation": {"agent_prompt": "Add a header."}},
            {"check_id": "VG-TLS-001", "remediation": {"agent_prompt": "Enforce TLS."}},
        ]

    monkeypatch.setattr(server_module, "get_scan_findings", fake_get_scan_findings)

    result = await get_fix_prompt("job-1", "VG-TLS-001")

    assert result == "Enforce TLS."


async def test_get_fix_prompt_raises_for_an_unknown_check_id(monkeypatch):
    async def fake_get_scan_findings(scan_job_id):
        return [{"check_id": "VG-HDR-001", "remediation": {"agent_prompt": "Add a header."}}]

    monkeypatch.setattr(server_module, "get_scan_findings", fake_get_scan_findings)

    with pytest.raises(VigiloApiError):
        await get_fix_prompt("job-1", "VG-NOT-REAL")
