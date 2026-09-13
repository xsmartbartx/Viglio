"""Vigilo scanner — the ARQ worker running in the isolated scan zone. Runs
`vigilo_orchestrator.jobs.run_scan_job`/`verify_ownership_job`: the only
process in the control plane that makes outbound requests to a target
(docs/architecture.md §3). `apps/api` never imports this app.
"""
