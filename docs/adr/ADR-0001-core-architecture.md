# ADR-0001: Core layered architecture

| Field | Value |
| --- | --- |
| Status | Accepted |
| Date | 2026-09-11 |

## Context

`docs/vision.md`, `docs/architecture.md`, `docs/modules.md` and
`docs/prooflight-vision-and-architecture.md` all already assume a five-layer
model — Core, Modules, Pipeline, Security, Documentation — and reference it as
"ADR 0001." That ADR was never actually written down. This document formalizes
what the other docs already treat as settled, so it has a canonical home
instead of being implicit across four files.

## Decision

Vigilo is organized into five layers:

| Layer | Responsibility | Realisation |
| --- | --- | --- |
| **Core** | Domain models, schema-first validation, sanitised logging, error taxonomy, config and brand-token loading, redaction | `packages/core` |
| **Modules** | The domain: probes, checks, scoring, reporting, monitoring, integrations, identity, project, billing | `packages/*` |
| **Pipeline** | Scan orchestration, job queue, scheduler, CI/CD | Scan Orchestrator, `apps/scanner` (Phase 1+) |
| **Security** | Scan authorisation, egress policy, rate governance, redaction gate, audit trail | `packages/security` |
| **Documentation** | This folder | `/docs` |

Hard rules, unchanged from the existing docs and restated here as the binding
version:

1. **Core has no business logic, no network, no database access, and no
   knowledge of any specific check, probe or provider.** Every other layer
   depends on Core; Core depends on nothing in this repository.
2. **Probes collect evidence; checks judge evidence; the two never import
   each other.** A probe issues requests and writes an immutable evidence
   bundle. A check is a pure function from that bundle to a finding.
3. **The component that touches the internet does nothing else.** Outbound
   requests to a target are isolated behind the Security layer's egress
   guard and never originate from the control plane.
4. **Every module validates its own input.** No module assumes upstream
   validation has already happened.
5. **All logging passes through Core's `log()`.** Redaction cannot be
   bypassed by a caller forgetting to sanitize before printing.

## Consequences

- New modules are added under `packages/` or `apps/` and must declare their
  dependency on Core (and, where relevant, Security) explicitly — no module
  reaches into another module's storage or internals directly.
- A module that needs another module's data does so through that module's
  published API, not through shared tables or shared mutable state.
- This ADR is extended, not replaced, by later architecture decisions
  (ADR-0002 onward). Changing the five-layer model itself requires a new ADR
  that explicitly supersedes this one.

## References

`docs/architecture.md`, `docs/modules.md`, `docs/vision.md`,
`docs/prooflight-vision-and-architecture.md` §5.1.
