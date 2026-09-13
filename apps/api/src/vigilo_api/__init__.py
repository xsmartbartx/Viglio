"""Vigilo API — the HTTP surface (docs/modules.md §12).

Phase 3 scope: anonymous scan submission (`/v1/scans`), Clerk-authenticated
account/target/ownership-verification endpoints. No domain logic in
handlers — every route validates, delegates to one module, and serialises
the result. This app must never import `vigilo_probes` (enforced by
`tests/test_no_egress_imports.py`): "the control plane never makes an
outbound request to a target, ever" (docs/architecture.md §3). All
target-touching work runs in `apps/scanner`'s ARQ worker, dispatched
through the queue, never called synchronously from here.
"""
