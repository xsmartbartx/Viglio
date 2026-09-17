"""The Vigilo MCP server — `run_scan`, `get_findings`, `get_fix_prompt` as
tools (docs/build-roadmap.md's Phase 9 entry, vision doc §12: "a genuine
distribution channel... the user fixes the finding without leaving their
editor"). Launched by an MCP client (e.g. Claude Desktop) as a subprocess
over stdio — `uv run vigilo-mcp` or `python -m vigilo_mcp.server`.

Lives at `apps/mcp`, not `packages/mcp` as the roadmap paragraph literally
names it — an MCP server is a process a client *launches*, like
`apps/cli`'s `vigilo scan`, not an importable library another package
depends on. Documented as a deviation in `docs/build-roadmap.md`, not a
silent rename.
"""

from __future__ import annotations

import asyncio

from mcp.server.mcpserver import MCPServer

from vigilo_mcp.client import (
    VigiloApiError,
    get_scan_findings,
    get_scan_report,
    get_scan_status,
    submit_scan,
)

_POLL_INTERVAL_SECONDS = 2.0
_MAX_WAIT_SECONDS = 90.0
_TERMINAL_STATUSES = {"complete", "unreachable", "failed", "rejected"}

server = MCPServer(name="vigilo")


@server.tool()
async def run_scan(target_url: str, requested_tier: str = "passive") -> dict:
    """Submit a Vigilo security/compliance scan of `target_url` and wait
    for it to complete, returning the full report. `requested_tier` is
    "passive" (default, no ownership proof needed) or "active" (only
    honored if the target has already been verified and the account's
    plan allows it — otherwise silently downgraded, never rejected).

    Waits up to ~90 seconds. If the scan is still running when that bound
    is hit, returns its current status instead of the report — call
    `get_findings` with the returned `scan_job_id` once it's done.
    """
    submission = await submit_scan(target_url, requested_tier)
    scan_job_id = submission["scan_job_id"]

    elapsed = 0.0
    while elapsed < _MAX_WAIT_SECONDS:
        status = await get_scan_status(scan_job_id)
        if status["status"] in _TERMINAL_STATUSES:
            if status["status"] == "complete":
                return await get_scan_report(scan_job_id)
            return {"scan_job_id": scan_job_id, "status": status["status"], "report": None}
        await asyncio.sleep(_POLL_INTERVAL_SECONDS)
        elapsed += _POLL_INTERVAL_SECONDS

    return {
        "scan_job_id": scan_job_id,
        "status": "still_running",
        "message": (
            "Scan is still running — call get_findings with this scan_job_id once it's done."
        ),
    }


@server.tool()
async def get_findings(scan_job_id: str) -> list[dict]:
    """List every finding from a completed scan, including passed and
    skipped checks — each with its severity, verdict, evidence (redacted),
    and remediation."""
    return await get_scan_findings(scan_job_id)


@server.tool()
async def get_fix_prompt(scan_job_id: str, check_id: str) -> str:
    """The paste-ready remediation prompt for one specific finding
    (`check_id`, e.g. "VG-HDR-001") from a completed scan — designed to be
    dropped directly into a coding assistant."""
    findings = await get_scan_findings(scan_job_id)
    for finding in findings:
        if finding["check_id"] == check_id:
            return finding["remediation"]["agent_prompt"]
    raise VigiloApiError(404, {"detail": f"no finding with check_id {check_id} on this scan"})


def main() -> None:
    server.run()


if __name__ == "__main__":
    main()
