# Build roadmap

## Purpose

The phase-by-phase build plan referenced by `README.md`'s "Getting started"
section. Adapted from `docs/prooflight-vision-and-architecture.md` §21, with
codenames replaced by the plain module names in `docs/modules.md` (per
ADR-0002) and each phase's "done when" kept as a concrete, testable exit
criterion rather than a percentage-complete estimate. Work proceeds one phase
at a time; a phase is not started until the previous one's exit criterion is
demonstrated.

---

## Phase 0 — Foundations ✅

Repository skeleton; `packages/core` (models, validation, logging, errors,
redaction, config); `packages/security`'s egress guard (SSRF/DNS-rebinding
defense); ADR-0001–0003; CI with a dedicated build-blocking egress-guard job;
local Docker Compose dev environment (Postgres, Redis, MinIO) — no third-party
accounts required.

**Done when:** the egress-guard suite is green in CI and demonstrably denies
loopback, private-range, cloud-metadata, CGNAT, multicast, reserved and
IPv4-mapped-IPv6 targets, without making a single real network request.

## Phase 1 — Engine core ✅

Target-URL validation wired into a real probe layer (`packages/probes`);
`httpx`-based HTTP client that connects to the egress guard's pinned IP,
never re-resolving; fingerprinting (framework/hosting/database-backend
detection from response signatures); the check layer (`packages/checks`) as
pure functions plus manifests, 20 `HDR`/`TLS` checks; scoring v1
(`packages/scoring`, deterministic, per the algorithm in
`docs/prooflight-vision-and-architecture.md` §7.3); a CLI (`apps/cli`, `vigilo
scan <url>`); local evidence storage (`LocalFileEvidenceStore`). No web
layer, no database, no billing — those are Phase 3+.

**Done when:** a scan of a local fixture target produces a byte-identical
score twice in a row (`apps/cli/tests/test_determinism.py`), and a scan of a
real, owned/public site produces at least one defensible, evidence-backed
finding (verified live against `example.com`: 6 findings, all TLS checks ran
and passed against the real handshake).

## Phase 2 — Registry to v0.1

Fill out `CLI` (client-side exposure), `EXP` (surface exposure), `SES`
(cookies/sessions), `DEP` (dependencies), `LEG` (legal documents) categories
to ~64 checks total. Check-descriptor format frozen (`CheckManifest` in
`packages/core/src/vigilo_core/models.py` already matches this shape).
`docs/check-catalog.md` generated from the descriptors, not hand-maintained.

**Done when:** every check has a golden-target fixture pair (known-good,
known-bad) and a primary-standard reference.

## Phase 3 — Control plane

`apps/api` grows real endpoints; PostgreSQL + SQLAlchemy + Alembic;
`identity`, `project` modules; `Account`/`Target`/`OwnershipProof` persistence;
`resolve_authorization()` and `verify_ownership()` implemented per ADR-0003
(fail-closed, audit-trail-first); anonymous free-scan path with email
capture; Redis + ARQ job queue between API and scan workers.

**Done when:** an unauthenticated visitor can scan a public site and receive
a report by email, and a target owner can complete DNS/file/meta-tag
verification and see their target upgrade to the active tier.

## Phase 4 — Report experience

Web report UI (Next.js), evidence panels, severity grouping, skipped-checks
transparency (a check that couldn't run is shown as such, never silently
passing — per the Phase 0 domain model's `Verdict.INCONCLUSIVE`), PDF export
via headless-browser render of the same HTML.

**Done when:** a non-technical reader can act on a report without asking a
clarifying question first.

## Phase 5 — Analysis layer (LLM)

Claude-backed report narrative and remediation-prompt generation
(`packages/reporting`), strictly additive per ADR-0001 rule 2 — it attaches
prose to findings that already exist and never creates, deletes, reclassifies
or re-ranks one. Redaction-gated prompt construction (nothing enters a prompt
unredacted). Template fallback when the provider is unavailable.

**Done when:** the LLM provider can be switched off entirely and the product
still ships a complete report from static remediation templates.

## Phase 6 — Active tier

Ownership-gated active checks: `APP` (application logic), `AUT`
(authentication surface), `INF` (infrastructure/DNS), `DAT` (data-platform
posture). Request-budget enforcement (§8.5 of the Prooflight doc). Registry
grows toward ~120 checks.

**Done when:** it is proven by test — not just by code review — that no
active-tier check is reachable against an unverified target under any code
path.

## Phase 7 — Monetisation

Three subscription tiers; billing via a merchant of record (Paddle or Lemon
Squeezy, per ADR-0002); entitlement snapshots enforced from one place
(`packages/billing`) rather than scattered per-feature checks; quotas;
ToS/AUP/privacy pages (Vigilo dogfoods its own `LEG`/`CMP` checks here).

**Done when:** entitlements are enforced from exactly one call site, and a
plan downgrade correctly and immediately restricts an active monitor.

## Phase 8 — Monitoring

Scheduler (`packages/monitoring`), scan diffing by finding fingerprint, score
history, alert dedupe/hysteresis/digest rules, embeddable score badge.

**Done when:** a deliberately reintroduced misconfiguration on a monitored
fixture produces exactly one `regressed` alert — not zero, not four.

## Phase 9 — Distribution

Public REST API + SSE; MCP server (`packages/mcp`) exposing `run_scan`,
`get_findings`, `get_fix_prompt`; read-only repository connector (secret and
dependency scanning, scored separately from the live-site score); white-label
reports and client workspaces; self-hostable engine container image.

---

## Standing rules across every phase

1. No check reaches the registry without a primary-standard reference, a
   golden-target fixture pair, documented false-positive conditions, and a
   `budget_cost`.
2. No change to the egress guard, the redaction chokepoint, or the
   authorization model ships without the change being called out explicitly
   in the PR/commit description.
3. Any scoring weight or severity change requires a registry version bump and
   a documented score-history discontinuity note.
4. Documentation is part of the change, not a follow-up — a change that
   alters a module's responsibility, API or dependency list updates
   `docs/modules.md` in the same change set.
