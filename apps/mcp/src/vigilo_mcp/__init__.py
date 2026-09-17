"""Vigilo MCP server: `run_scan`/`get_findings`/`get_fix_prompt` exposed as
MCP tools, a thin `httpx` client of the public REST API
(`docs/build-roadmap.md`'s Phase 9 entry) — no `vigilo_*` dependency.
"""

from __future__ import annotations
