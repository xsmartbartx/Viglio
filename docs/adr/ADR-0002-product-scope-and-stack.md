# ADR-0002: Product scope, brand resolution, and runtime stack

| Field | Value |
| --- | --- |
| Status | Accepted — see the Phase 4 addendum below |
| Date | 2026-09-11 |

## Context

Two overlapping specs existed in `docs/`: the established Vigilo documents
(`README.md`, `docs/vision.md`, `docs/architecture.md`, `docs/modules.md`,
`brand.config.json`) and a draft, `docs/prooflight-vision-and-architecture.md`,
proposing a different brand, module codenames (`lantern-engine`,
`atlas-registry`, `pulse-scheduler`), check-ID prefix (`PF-`) and repository
layout (`src/` instead of `apps/` + `packages/`). Building against both would
mean redoing work; a decision was needed before any code could be written.

Separately, `docs/architecture.md` §5 specifies Python 3.12, but the
development machine has Python 3.11.9 available via pyenv (confirmed
2026-09-11) and no 3.12 installation.

## Decision

**Brand and layout: Vigilo.** Product name, module names (`probes`, `checks`,
`scoring`, `reporting`, `security`, …) and repository layout (`apps/*`,
`packages/*`) follow the established, non-draft docs. `brand.config.json`
remains the single source of truth for user-visible naming — nothing
hardcodes "Vigilo" in source code paths that should read from it.

**Detail merged in from the Prooflight draft:** its more concrete build-phase
plan, domain-model field tables (§6.1), and check-descriptor format (§7.1)
are adopted, translated onto Vigilo naming. Check IDs use `VG-<CAT>-<NNN>`
(e.g. `VG-HDR-014`), not `PF-<CAT>-<NNN>`. Engine codenames (`lantern`,
`atlas`, `pulse`) are **not** adopted; modules keep the plain names from
`docs/modules.md` ("Scan Orchestrator," "Monitor Scheduler," etc.).

**Stack**, per `docs/architecture.md` §5, unchanged:

| Concern | Choice |
| --- | --- |
| API | Python + FastAPI + Pydantic v2 |
| Frontend | Next.js + TypeScript + Tailwind (Phase 3+) |
| Queue | Redis + ARQ |
| Database | PostgreSQL + SQLAlchemy + Alembic (Phase 3+) |
| Object storage | S3-compatible — MinIO locally, R2 or equivalent in production |
| Headless browser | Playwright (Phase 1+, `render`/`bundle` probes) |
| Auth | Managed provider (Clerk or Supabase Auth) — deferred until an account model exists (Phase 3) |
| Billing | Merchant of record (Paddle or Lemon Squeezy) — deferred to Phase 7 |
| Email | Transactional provider (Resend or Postmark) — deferred to Phase 3+ |
| Package management | `uv` workspace, single lockfile, one shared venv |

**Python version deviation.** Target `>=3.11` for now rather than requiring
3.12, since that's what's actually installed. Nothing built so far uses a
3.12-only feature. Revisit when either (a) a 3.12-only feature is genuinely
needed, or (b) production deployment is provisioned and can pin 3.12
directly — whichever comes first. This is a pragmatic accommodation, not a
silent divergence: it's recorded here precisely so it doesn't get forgotten.

## Consequences

- Any future contributor reading `docs/prooflight-vision-and-architecture.md`
  should treat it as superseded for naming/layout purposes; its phase plan,
  domain model and check format remain the reference until folded into
  `docs/build-roadmap.md`, `docs/data-model.md` and `docs/check-catalog.md`
  respectively (as those are written, phase by phase).
- Every third-party account this stack eventually needs (Clerk/Supabase,
  Paddle/Lemon Squeezy, Resend/Postmark, a cloud host) is deliberately not
  provisioned yet — Phase 0 requires none of them and runs entirely on local
  Docker services.

## Addendum (Phase 4): implementation decisions

Five judgment calls made while actually building the report experience,
recorded here per the same standing rule as ADR-0003's Phase 2/3 addenda.

**Playwright's actual first production use is PDF export via a live-page
render, not the `render`/`bundle` probes this ADR originally earmarked it
for.** Those probes ended up built on `httpx` instead (Phase 1/2) — a
headless browser turned out not to be needed to collect evidence, only to
*present* it. `packages/reporting/src/vigilo_reporting/pdf.py`'s
`render_pdf()` launches a real Chromium instance and navigates
`{WEB_APP_URL}/reports/{scan_job_id}?print=1`, matching the Prooflight
doc's "one layout source of truth" framing rather than standing up a
second, server-templated HTML system. The stack table's line above is now
historical intent, not current fact — corrected in spirit here rather than
rewritten, per this document's own append-only addendum convention.

**This introduces a new runtime coupling: `apps/scanner`'s ARQ worker now
needs outbound network access to wherever `apps/web` is deployed.** Before
Phase 4, the worker's only network target was the scan target itself
(egress-guarded) plus Postgres/Redis/MinIO/Postmark. `WEB_APP_URL` is a
new, unguarded (no egress-guard check) HTTP dependency — acceptable because
it points at Vigilo's own frontend, a trusted first-party service, not
attacker-controlled input; nothing egress-guard-worthy about a fixed,
operator-configured URL. Production deployment must ensure the worker's
network policy allows this one first-party destination.

**`apps/api` gained its first CORS surface**, scoped to exactly
`WEB_APP_URL` (`vigilo_api/main.py`), added conditionally only when that
env var is set. Before Phase 4 nothing in `apps/api` was ever called from a
browser directly (`apps/web`'s server components proxy every request
server-to-server); Phase 4's `ExportPdfButton`/`ShareLinkManager` client
components are the first code to call `apps/api` from inside a browser, for
the two flows that need a live Clerk session token client-side.

**`render_badge()` ships this phase as a pure function only — no API
route, no caching, no embed page.** `docs/build-roadmap.md` already places
the embeddable score badge at Phase 8, where `brand.config.json`'s
already-reserved `badgePath` gets consumed; building a route for it now
would be scope creep against a phase that isn't ready for it (no monitoring,
no stable public score history to badge against yet).

**No free-tier gating on the report itself.** The Phase 4 plan considered
showing only the first finding to anonymous readers and gating the rest
behind a paywall, but Phase 7 (Monetisation) is what actually builds
entitlement enforcement (`packages/billing`, one call-site rule) — adding
an ad hoc gate here would mean a second enforcement path to later reconcile
with that one. The report renders unconditionally this phase, matching how
Phase 3 already treats every scan.
