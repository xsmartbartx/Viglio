# Vigilo

Live security and compliance scanning for AI-generated web apps.

Vigilo takes a deployed URL (or a repository), gathers evidence about it the way an
outside visitor would, runs a versioned catalogue of deterministic checks against that
evidence, and returns a prioritised, plain-language report with a paste-ready fix for
every finding. It then keeps re-running the same scan on a schedule and alerts the owner
when the result gets worse.

Built for apps shipped from Lovable, Cursor, Bolt, v0, Replit, Windsurf and Claude Code,
where the generated backend defaults — public tables, client-bundled keys, missing
headers, no legal pages — are the same handful of mistakes over and over.

---

## Why this exists

AI coding tools produce working apps faster than their authors can learn what a working
app is supposed to protect. The result is a predictable failure set:

- database rows readable by anyone with the public anon key,
- provider API keys compiled into the JavaScript bundle by a `VITE_` / `NEXT_PUBLIC_` prefix,
- staging and preview deployments left publicly reachable,
- no Content-Security-Policy, no HSTS, no rate limiting on auth routes,
- no privacy policy, no cookie consent, analytics firing on first paint in the EU.

Generic vulnerability scanners are built for hand-written enterprise software and report
hundreds of low-value findings. Vigilo runs a smaller catalogue tuned to what these
specific generators emit, and explains each result in terms the person who typed the
prompt can act on.

---

## Product surface

| Surface | What it is |
| --- | --- |
| Web app | Scan submission, live scan stream, report, score history, project management |
| Report | Shareable HTML report + PDF export + embeddable score badge |
| Monitoring | Scheduled re-scans, regression alerts, score history |
| Public API | REST + SSE, API-key authenticated, same engine as the web app |
| MCP server | `vigilo-mcp` — lets Cursor / Claude Code start scans and pull findings in-editor |
| CLI | `vigilo scan <url>` for CI pipelines and local use |

---

## Repository structure

```text
.github/
  ├─ copilot-instructions.md
  └─ agents/
       ├─ architecture.agent.md
       ├─ documentation.agent.md
       ├─ pentest.agent.md
       └─ scan-engine.agent.md        # new — owns the check catalogue
.copilot/
  └─ prompts/
       ├─ architecture.prompt.md
       ├─ documentation.prompt.md
       ├─ refactor.prompt.md
       └─ check-authoring.prompt.md   # new — authoring a single check
apps/
  ├─ web/                             # Next.js frontend (Phase 4)
  ├─ api/                             # FastAPI control plane
  ├─ cli/                             # `vigilo scan <url>`
  └─ scanner/                         # ARQ worker (isolated network zone — the only
                                       #   control-plane process that imports probes)
packages/
  ├─ core/                            # models, validation, logging, errors, config
  ├─ persistence/                     # SQLAlchemy Base, async engine/session, Alembic
  ├─ security/                        # egress guard, scan authorization, ownership
                                       #   verification, audit trail
  ├─ identity/                        # accounts, Clerk mapping
  ├─ project/                         # projects, targets, ownership proofs
  ├─ probes/                          # evidence collectors
  ├─ checks/                          # pure check functions + manifests
  ├─ scoring/                         # deterministic score model
  ├─ orchestrator/                    # scan lifecycle: state machine + ARQ jobs
  ├─ integrations/                    # Postmark (email), MinIO/S3 (object storage)
  ├─ reporting/                       # HTML/PDF/badge rendering (Phase 4)
  └─ mcp/                             # MCP server (Phase 9)
docs/
  ├─ vision.md
  ├─ architecture.md
  ├─ modules.md
  ├─ check-catalog.md
  ├─ data-model.md
  ├─ api.md
  ├─ security.md
  ├─ build-roadmap.md
  └─ adr/
       ├─ ADR-0001-core-architecture.md
       ├─ ADR-0002-product-scope-and-stack.md
       └─ ADR-0003-scan-authorization-model.md
brand.config.json                     # single source of truth for naming
```

---

## Architecture in one paragraph

Five layers, as defined in ADR 0001. The **Core Layer** holds models, schema-first
validation and sanitised logging. The **Modules Layer** holds the domain: probes, checks,
scoring, reporting, monitoring, integrations. The **Pipeline Layer** orchestrates scans as
queued jobs and runs CI/CD. The **Security Layer** enforces scan authorisation, egress
policy, rate governance and the audit trail. The **Documentation Layer** is this folder.

The one non-obvious decision: **probes collect evidence, checks judge evidence, and the
two never touch each other.** A probe issues network requests and writes an immutable
evidence bundle. A check is a pure function from that bundle to a finding. Every check is
therefore replayable offline, unit-testable without a network, and deterministic — the
same evidence always produces the same report. See `docs/scan-engine.md`.

---

## Branding

Every user-visible name comes from `brand.config.json`. Nothing hardcodes the product name
in source. Renaming the product is a one-file change plus a rebuild.

Alternative names held in reserve: **Prooflight**, **Latch**, **Bezpiecznik**.

---

## Security model

Vigilo sends real HTTP requests to third-party infrastructure, so authorisation is a
first-class architectural concern, not a checkbox.

- **Tier 0 (unverified)** — passive checks only. Vigilo requests exactly what a normal
  browser visiting the homepage would request. No hidden-path enumeration, no auth probing.
- **Tier 1 (verified owner)** — full active scan. Ownership is proved by DNS `TXT` record,
  a `/.well-known` token file, a meta tag, or connected repository write access.
- Never — destructive methods, credential guessing, payload fuzzing, or scanning of
  denylisted infrastructure.

See `docs/security.md` and ADR 0003.

---

## Getting started

1. Read `docs/vision.md` — what is being built and for whom.
2. Read `docs/architecture.md` and `docs/adr/ADR-0002-product-scope-and-stack.md` — the shape and the stack.
3. Read `docs/modules.md` — the module contracts each package implements.
4. Follow `docs/build-roadmap.md` — phase by phase, each independently demonstrable.

---

## Local development

Requires [`uv`](https://docs.astral.sh/uv/), Docker, and Docker Compose. Real
Clerk/Postmark/Anthropic accounts are only needed to exercise auth/email/
LLM-backed remediation end to end — everything else runs locally with no
third-party accounts, and a scan completes with template-based remediation
text if `ANTHROPIC_API_KEY` is unset (a hard availability requirement, not
a fallback of convenience — see `docs/adr/ADR-0004-llm-boundary.md`).

```bash
cp .env.example .env            # fill CLERK_SECRET_KEY/CLERK_JWKS_URL/POSTMARK_SERVER_TOKEN/
                                 # ANTHROPIC_API_KEY to exercise auth/email/LLM remediation;
                                 # WEB_APP_URL defaults to http://localhost:3000 (apps/web
                                 # below) — the rest works with no third-party accounts at all
uv sync --all-packages          # installs every package/app into one .venv
uv run playwright install chromium   # one-time: the PDF-export render target
docker compose up -d            # postgres, redis, minio — bound to localhost only
uv run alembic -c packages/persistence/alembic.ini upgrade head   # create the schema
uv run pytest -q                # full test suite, including both build-blocking suites
                                 # — runs against DATABASE_URL, resetting its schema each
                                 # time (packages/persistence's temporary_schema() fixture);
                                 # re-run the alembic command above afterwards if you want
                                 # your local dev data back.
uv run ruff check .
uv run vigilo scan https://example.com     # a real, live scan end to end, no persistence
uv run arq vigilo_scanner.worker.WorkerSettings   # the ARQ worker (no --app-dir — every
                                                   # workspace package installs into the
                                                   # one shared .venv `uv sync` builds)
uv run uvicorn vigilo_api.main:app --reload --app-dir apps/api/src         # the control plane
```

Then `curl http://localhost:8000/healthz` and `curl http://localhost:8000/version`, or
`curl -X POST http://localhost:8000/v1/scans -d '{"target_url":"https://example.com","email":"you@example.com"}'`
for the full anonymous-scan flow (needs the worker running to actually complete).

**`apps/web`** (Phase 4, Next.js — needs Node per `apps/web/.nvmrc`):

```bash
cp apps/web/.env.example apps/web/.env.local   # fill in Clerk keys — `npx clerk@latest init`
                                                # (run from apps/web) provisions a free
                                                # throwaway dev instance non-interactively,
                                                # no dashboard account needed, and writes
                                                # NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY/
                                                # CLERK_SECRET_KEY straight into .env.local;
                                                # copy CLERK_SECRET_KEY into the root .env
                                                # too (apps/api verifies the same tokens) —
                                                # derive CLERK_JWKS_URL from the publishable
                                                # key's frontend-API host, i.e.
                                                # https://<that-host>/.well-known/jwks.json.
                                                # Then create the `vigilo-api` JWT template
                                                # (with an `email` claim) either in the Clerk
                                                # dashboard or via
                                                # `npx clerk@latest api /jwt_templates -d
                                                # '{"name":"vigilo-api","claims":{"email":
                                                # "{{user.primary_email_address}}"}}'`.
cd apps/web && npm install && npm run dev      # http://localhost:3000
```

Stop the local infra with `docker compose down` when done.

---

## Status

**Phase 6 (Active tier, scoped) complete.** Every check now runs behind a
real, two-layer tier gate: an unverified target's scan never even makes
the `paths` probe's hidden-path-enumeration requests (probe layer), and an
active-tier-only check is never in the list evaluated at all for a passive
scan (check layer) — proven by a new build-blocking CI suite,
`tier-gating-suite`, matching the egress-guard/ownership-verification
standard. This closed a real, previously-undocumented gap: nothing had
ever acted on a scan's granted tier before, so the moment any active-tier
check existed it would have run against every scan regardless of
verification. Seven of those checks now exist — `VG-EXP-006`..`012`,
deferred from Phase 2 (repository metadata, backup artefacts, exposed
config, debug/test routes, directory listing, default admin panels), via a
new `paths` probe with a small, fixed candidate list. A second,
independent gap surfaced and got fixed in the same phase:
`apps/api`'s scan-submission endpoint was hardcoding "unverified" into
every authorization check, so no scan could ever actually be granted
active tier — fixed for returning, already-verified submitters, without
touching first-time submitters' existing "deny leaves no account behind"
behavior. `APP`/`AUT`/`INF` (three more roadmap-named categories) are
deliberately deferred to their own follow-up — see
`docs/build-roadmap.md`'s Phase 6 entry for why.

**Phase 5 (Analysis layer / LLM).** Every failed finding now gets
Claude-backed, structured remediation — `explanation`/`impact`/ordered
`remediation_steps`/an `estimated_effort` badge/a copy-to-clipboard
`agent_prompt` block (`apps/web`'s `FindingCard`/`AgentPromptBlock`) — the
README's headline "paste-ready fix for every finding" promise, built for
real. Generation happens in a new background job
(`generate_remediations_job`) auto-enqueued right after scan scoring, never
inline in the scan pipeline, so a scan's completion and a report's ability
to render never depend on LLM availability or latency
(`docs/adr/ADR-0004-llm-boundary.md`'s hard rule). Results cache by
`(fingerprint, registry_version)` in a new `remediation_cache` table, so a
repeat scan of the same target skips the LLM entirely on a cache hit.
Redaction is allowlist-based (an explicit, reviewed field list — never
`target_origin`, never the raw evidence bundle) and the model's JSON
response is strictly schema-validated and discarded whole on any failure,
falling back to the same deterministic template text Phase 4 always
rendered — verified by actually running a scan with `ANTHROPIC_API_KEY`
unset and confirming every finding still shows `source: "template"`. The
one thing not driven live this phase is the actual Claude-generated path
itself (no API key was available) — see `docs/build-roadmap.md`'s Phase 5
entry for exactly what covers that gap instead.

**Phase 4 (Report experience).** `apps/web` is the repo's first
TypeScript app (Next.js 16 + Clerk) and gives a scan an actual face: a
public `/reports/{scanId}` page with score, severity-grouped findings,
remediation text, evidence panels, and `COULDN'T CHECK`/`NOT APPLICABLE`
rendered as two distinct, honestly-labelled sections — never silently
folded into "passed." A new `packages/reporting` renders that same data as
pure functions (`build_report`) and exports it to PDF by driving Playwright
against the *live* web page (`?print=1`), one layout source of truth rather
than a second templating system. `reports`/`share_links` joined the schema
(`docs/data-model.md`): the full `ShareLink` entity (hashed, expiring,
revocable tokens with view counts) ships additively on top of Phase 3's
no-login scan-UUID access, not a replacement for it. A real gap surfaced
and got fixed this phase too — `Finding.evidence` was computed at
check-evaluation time but silently dropped before persistence; `findings`
now has `matched_indicator`/`request_summary`/`redaction_applied` columns,
with the `redaction_applied`-always-`False` producer-side gap documented,
not silently shipped as if fixed. See `docs/build-roadmap.md`'s Phase 4
entry for exactly what was verified live (including a real
id-confusion bug the PDF pipeline shipped with, found and fixed during that
pass) and the one gap that wasn't (the full Clerk sign-in flow, blocked by
a bot-check this project won't attempt to solve).

**Phase 3 (Control plane).** `apps/api` is a real control plane, not a
bootstrap: anonymous scan submission with email delivery
(`POST /v1/scans`), Clerk-authenticated accounts/targets, and the full
DNS/file/meta-tag ownership-verification flow (`docs/api.md`). Persistence
arrived via a new `packages/persistence` (async SQLAlchemy + Alembic) —
`Account`/`Project`/`Target`/`OwnershipProof`/`ScanJob`/`Scan`/`Finding`/
`AuditEvent` across 8 tables (`docs/data-model.md`). `resolve_authorization()`
and `verify_ownership()` are real, in `packages/security`, both fail-closed
and both covered by their own build-blocking CI suite (the new
`ownership-verification-suite`, alongside the original `egress-guard-suite`).
The append-only audit trail is enforced at the database level by a Postgres
trigger, not just application discipline. A real `packages/orchestrator`
(replacing Phase 1's CLI-only convenience wrapper) drives the scan lifecycle
as ARQ jobs, run by a new `apps/scanner` worker — the only control-plane
process that talks to a target, enforced by a static import-boundary test.
`packages/integrations` added Postmark (email) and MinIO/S3 (evidence
storage). Both Phase 3 exit criteria run end to end locally against real
Postgres/Redis/MinIO.

Still ahead: LLM-authored report narrative, and the active-tier checks that
verified ownership already unlocks but the registry doesn't populate yet —
see `docs/build-roadmap.md` for what's next. All documents in `/docs` are
authoritative for implementation and must be updated by the responsible
agent whenever behaviour changes.

## Licence

Apache 2.0. Automated assessments only — not legal advice and not a substitute for a
manual penetration test.
