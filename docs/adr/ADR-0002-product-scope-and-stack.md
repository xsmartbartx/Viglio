# ADR-0002: Product scope, brand resolution, and runtime stack

| Field | Value |
| --- | --- |
| Status | Accepted |
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
