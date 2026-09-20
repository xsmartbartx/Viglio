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
| Web app | Scan submission, live scan stream, report, score history, and a self-serve dashboard (targets, billing, API keys, branding) |
| Report | Shareable HTML report + PDF export + embeddable score badge |
| Monitoring | Scheduled re-scans, regression alerts, score history |
| Public API | REST + SSE, API-key authenticated, same engine as the web app |
| MCP server | `vigilo-mcp` — lets Cursor / Claude Code start scans and pull findings in-editor |
| CLI | `vigilo scan <url>` for CI pipelines and local use — `--sarif`/`--fail-on` for CI gating |
| GitHub Action | `.github/actions/scan` — zero-account CI scan, uploads SARIF to Code Scanning |

---

## Repository structure

```text
.github/
  ├─ copilot-instructions.md
  ├─ workflows/ci.yml
  ├─ actions/
  │    └─ scan/action.yml             # this repo's first custom GitHub Action — wraps
  │                                   #   apps/cli/Dockerfile for zero-account CI
  │                                   #   scanning + SARIF upload, see docs/github-action.md
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
  ├─ cli/                             # `vigilo scan <url>` — --sarif/--fail-on for CI,
                                       #   Dockerfile is .github/actions/scan's engine
  ├─ scanner/                         # ARQ worker (isolated network zone — the only
                                       #   control-plane process that imports probes);
                                       #   also owns the monitoring cron/diff job bodies
                                       #   (Phase 8 — avoids a package-level dependency
                                       #   cycle, see docs/modules.md §9)
  └─ mcp/                             # MCP server (Phase 9) — apps/, not packages/: it's a
                                       #   launched process (like apps/cli), not a library
                                       #   another package imports; zero vigilo_* dependencies,
                                       #   a thin httpx client of apps/api's public REST API
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
  ├─ integrations/                    # Postmark (email), MinIO/S3 (object storage),
                                       #   Anthropic (LLM remediation), Paddle (billing)
  ├─ reporting/                       # HTML/PDF/badge rendering (Phase 4)
  ├─ billing/                         # entitlements + quota decisions, pure (Phase 7)
  ├─ monitoring/                      # scheduling, scan diffing, alerts (Phase 8)
  └─ notification/                    # renders and sends alert emails (Phase 8)
docs/
  ├─ vision.md
  ├─ architecture.md
  ├─ modules.md
  ├─ check-catalog.md
  ├─ data-model.md
  ├─ api.md
  ├─ security.md
  ├─ self-hosting.md                  # Phase 9
  ├─ github-action.md                 # .github/actions/scan usage
  ├─ build-roadmap.md
  └─ adr/
       ├─ ADR-0001-core-architecture.md
       ├─ ADR-0002-product-scope-and-stack.md
       └─ ADR-0003-scan-authorization-model.md
docker-compose.yml                    # local dev infra only (postgres/redis/minio)
docker-compose.self-host.yml          # Phase 9 — the full self-hosted stack, see docs/self-hosting.md
Caddyfile                             # reverse proxy + automatic HTTPS for a production VPS deployment
scripts/deploy.sh                     # idempotent redeploy: git pull, rebuild, migrate
scripts/backup.sh                     # Postgres + MinIO evidence backup to a timestamped tarball
SECURITY.md                           # vulnerability disclosure policy
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
Clerk/Postmark/Anthropic/Paddle accounts are only needed to exercise
auth/email/LLM-backed remediation/live billing end to end — everything else
runs locally with no third-party accounts, and a scan completes with
template-based remediation text if `ANTHROPIC_API_KEY` is unset (a hard
availability requirement, not a fallback of convenience — see
`docs/adr/ADR-0004-llm-boundary.md`). Billing (`PADDLE_*`) is stubbed by
design this phase — see Status below — so leaving it unset is the normal
case, not a degraded one; `POST /v1/billing/checkout`/`webhook` raise a
`BILLING_PROVIDER_ERROR` (500) if called without it configured, same
"works without it, fails loudly if called anyway" pattern as the other
optional providers.

```bash
cp .env.example .env            # fill CLERK_SECRET_KEY/CLERK_JWKS_URL/POSTMARK_SERVER_TOKEN/
                                 # ANTHROPIC_API_KEY/PADDLE_* to exercise auth/email/LLM
                                 # remediation/billing; WEB_APP_URL defaults to
                                 # http://localhost:3000 (apps/web below) — the rest works
                                 # with no third-party accounts at all
uv sync --all-packages          # installs every package/app into one .venv
uv run playwright install chromium   # one-time: the PDF-export render target
docker compose up -d            # postgres, redis, minio — bound to localhost only
uv run alembic -c packages/persistence/alembic.ini upgrade head   # create the schema
uv run pytest -q                # full test suite, including all four build-blocking suites
                                 # — runs against DATABASE_URL, resetting its schema each
                                 # time (packages/persistence's temporary_schema() fixture);
                                 # re-run the alembic command above afterwards if you want
                                 # your local dev data back.
uv run ruff check .
uv run vigilo scan https://example.com     # a real, live scan end to end, no persistence
uv run arq vigilo_scanner.worker.WorkerSettings   # the ARQ worker (no --app-dir — every
                                                   # workspace package installs into the
                                                   # one shared .venv `uv sync` builds).
                                                   # Also runs check_due_monitors_job as an
                                                   # ARQ cron job (every 15 min, Phase 8) —
                                                   # nothing extra to start for monitoring.
uv run uvicorn vigilo_api.main:app --reload --app-dir apps/api/src         # the control plane
```

**`apps/mcp`** (Phase 9 — needs a real API key, not a Clerk session):
create one via `POST /v1/me/api-keys` on a paid-plan account (Free's
`api_keys_limit` is `0`), then:

```bash
export VIGILO_API_BASE_URL=http://localhost:8000   # apps/api's own origin, default shown
export VIGILO_API_KEY=vglo_...                      # the plaintext returned once at creation
uv run vigilo-mcp                                   # stdio MCP server — point Claude
                                                     # Desktop/an MCP inspector at this command
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

## Self-hosting

Vigilo also ships as three container images
(`apps/api`/`apps/scanner`/`apps/web`) you can run on your own
infrastructure instead of using the hosted product — see
`docs/self-hosting.md` for the full build/run instructions and required
environment variables. A bundled `caddy` service and `scripts/deploy.sh`
cover a real production VPS deployment with a domain and automatic TLS —
see that doc's "Production VPS deployment" section.

---

## Status

**Gap closure: abuse-rate ceiling, finding suppression, disclosure policy,
backups (post-Phase-9).** A pre-deployment review found four addressable
gaps and closed all of them. (1) `resolve_authorization()`'s 24-hour
abuse-rate ceiling (`docs/security.md` §3) was implemented and tested but
never fed a real count — every caller passed `recent_scan_count_24h=0`. A
new `count_scan_jobs_for_target_since()` (`packages/orchestrator`) now
feeds it a real per-target count at all three call sites. (2) A
target-scoped suppression/"accepted risk" workflow closes the vision
doc's never-built `acknowledged`/`muted` finding states
(`docs/prooflight-vision-and-architecture.md` §6.2) — a new `Suppression`
entity (`packages/project`) applied at report rendering (marked, not
removed), SARIF export (excluded entirely, complementing GitHub's own
alert-dismissal workflow), and monitoring alerts (no new-critical/
regressed noise for something already accepted), deliberately **never**
at scoring — a suppressed finding still counts toward the score, so the
number stays the one true, unfiltered signal. Managed via
`/v1/targets/{id}/findings/suppress` and a new "Accepted risks" section
on the report page. (3) `SECURITY.md` adds a vulnerability disclosure
policy with a safe-harbor clause for good-faith research. (4)
`scripts/backup.sh` backs up both stateful volumes (a `pg_dump -Fc` plus
a MinIO evidence tar) to one timestamped, cron-friendly tarball
(`docs/self-hosting.md`'s Backups section).

**SARIF export, CWE mapping, and a GitHub Action (post-Phase-9).** A full
CWE audit assigned a taxonomy identifier to 51 of the 64 checks (the
other 13 are compliance/legal-linkage checks, deliberately left
unmapped — see `docs/check-catalog.md`'s CWE column and
`docs/build-roadmap.md` for the full per-check reasoning). A new
`build_sarif_report()` (`packages/reporting`) renders findings as SARIF
2.1.0 — validated against the real, official SARIF JSON schema, not just
eyeballed. `.github/actions/scan` (this repo's first custom GitHub
Action) wraps the standalone `vigilo` CLI (`apps/cli/Dockerfile`, new) for
zero-account CI distribution — no signup, drop it into a workflow, get
results in GitHub's Security tab; `POST /public/v1/scans` also gained a
`.../report.sarif` endpoint for API-key customers wiring CI into their
persisted/monitored scans specifically. New CLI flags `--sarif`/
`--fail-on` produce both the SARIF content and the CI pass/fail decision
from one live scan. See `docs/github-action.md` for usage and the honest
caveat about SARIF's file/line model not cleanly fitting live-URL
findings.

**Self-serve dashboard added (post-Phase-9).** A live end-to-end pass after
Phase 9 confirmed the scan engine genuinely works but found `apps/web` had
no UI for any account-level feature beyond one deep-linked monitoring
page — no target list, no way to add a target or start ownership
verification, and no way to actually give Vigilo money (`POST
/v1/billing/checkout` existed with nothing in the UI ever calling it). A
new `/dashboard` section closes this: an overview, a target list with
inline ownership-verification (DNS TXT / well-known file / meta tag), a
billing/upgrade page (plan comparison table, no invented prices — the real
price lives only in Paddle's hosted checkout, reached via the existing
endpoint), API key management (create/list/revoke, plaintext shown once),
and Business-tier branding settings. Two small endpoints were added to
support it, `GET /v1/targets` and `GET /v1/plans` (`docs/api.md`);
everything else reuses existing, already-tested backend surface as-is. The
three existing pages' shared header markup was extracted into
`components/Header.tsx` for the new section to use, without retrofitting
the shipped pages themselves — a small, deliberate follow-up, not bundled
into this change.

**Phase 9 (Distribution, scoped) complete.** Vigilo is programmatically
reachable now, not only through the web app: a key-authenticated public
REST API + SSE (`/public/v1/*`, scoped by `scan:run`/`scan:read`/
`project:read`/`report:read`/`monitor:read`/`monitor:write`, rate-limited
per account) and an MCP server (`apps/mcp`, `uv run vigilo-mcp`) exposing
`run_scan`/`get_findings`/`get_fix_prompt` as tools — "the user fixes the
finding without leaving their editor," built for real. A new **Business**
plan tier adds white-label reports (a `BrandingProfile`'s logo/color/
footer on both the report page and share links) — introduced to resolve a
real contradiction between two sections of the vision doc about which
tier owns this feature, which also surfaced and fixed a latent bug:
`api_keys_limit` was silently unlimited on every plan (including Free)
until this phase gave every plan an explicit value. Three self-hostable
container images (`apps/api`/`apps/scanner`/`apps/web`, Next.js's
`output: "standalone"` mode for the web image) plus
`docker-compose.self-host.yml` ship this phase too, built and run
end-to-end against real infrastructure during verification, not only
reviewed — see `docs/self-hosting.md`. The roadmap's fifth Phase 9
initiative, a read-only repository connector, is explicitly deferred to
its own future phase: research during planning found it's a wholly new
subsystem (GitHub auth, a new evidence source, new scanning logic)
comparable in size to Phase 7 or 8 by itself, not a natural extension of
anything else this phase built. See `docs/build-roadmap.md`'s Phase 9
entry for the full account, including a `uv sync --frozen` footgun this
project had already documented once and then re-hit while writing the
new Dockerfiles, caught and fixed the same way (`--all-packages`).

**Phase 8 (Monitoring) complete — built in full, not scoped down.** Vigilo
is continuous now: a scheduler (`packages/monitoring`, an ARQ cron job
every 15 minutes) re-scans monitored targets, diffs each new scan against
the last by finding fingerprint, and alerts on what changed —
`new_critical`/`new_high` (a fingerprint failing for the first time ever),
`regressed` (failing again after being resolved — distinguished from
"new" by a fingerprint history query spanning every prior scan, not just
the immediately preceding one), `cert_expiry` (reusing the existing
`VG-TLS-004` check's data, no new TLS read), `score_drop` (hysteresis-
gated — confirmed only on a second consecutive drop, or immediately
alongside a critical finding), and `scan_failed`. A new
`packages/notification` renders and emails alerts, batching more than five
into one digest per the vision doc's rule. `packages/billing` gained a
`MONITORS` per-plan limit (monitored scans themselves don't consume the
`SCANS_MONTHLY` quota — a deliberate product decision, not an oversight).
A real architectural problem surfaced during planning and got solved
cleanly: `packages/monitoring` depends on `packages/orchestrator`, so the
new job bodies live in `apps/scanner` instead of alongside the other ARQ
jobs, reached by ARQ's string-based `enqueue_job` rather than a Python
import, keeping the package dependency graph acyclic. `apps/web` gained a
full monitoring dashboard — toggle, cadence/quiet-hours controls, a
hand-rolled inline-SVG score-history chart (no new charting dependency),
an alert timeline, and a badge-embed snippet for `GET /badge/{target_id}.svg`
(public, embeddable, already-built `render_badge()` from Phase 7 finally
wired to a route). Verified by test, not just review, against the exact
roadmap wording: a fingerprint failing, resolving, then failing again
produces exactly one `regressed` alert, never `new_critical`, never more
than one — now its own build-blocking CI job,
`regression-diff-suite`. See `docs/build-roadmap.md`'s Phase 8 entry for
the full account, including what could and couldn't be verified live (the
authenticated dashboard render hit the same Clerk bot-check that's blocked
full UI verification since Phase 4).

**Phase 7 (Monetisation, scoped) complete.** `Account.plan_id` is real now:
three static plans (Free/Builder/Studio) enforced from one place
(`packages/billing`'s `entitlements()`/`consume()`, pure functions over
primitives, matching the precedent `resolve_authorization`/`build_report`
already set) against what exists today — target count, scans/month,
passive-vs-active tier, share-link export. A new, provider-agnostic
checkout/webhook adapter (`packages/integrations`'s Paddle client +
`apps/api`'s `/v1/billing` routes) is stubbed by design — no real Paddle
account, verified against a locally-computed, validly-signed mock webhook,
same DI-seam pattern as Postmark/Clerk/Anthropic. A real, previously-latent
quota bypass surfaced and got fixed in the same phase: scan submission for
a returning account was creating new `Target` rows with no quota check at
all, independent of `POST /v1/targets`' own check — both paths now enforce
the same limit. Real, clearly-labeled draft legal pages (Privacy/Terms/
Cookies/AUP, with a persistent "not reviewed by a lawyer" banner) ship with
a new site footer, dogfooding Vigilo's own passive `LEG` checks — verified
by running the actual `Check.evaluate()` functions against the live
homepage HTML. See `docs/build-roadmap.md`'s Phase 7 entry for the full
account: the live, end-to-end proof that a webhook-driven plan upgrade
immediately unlocks active tier for an otherwise-identical request, the
Phase 6 regression this phase's own plan gate would have introduced (and
its fix), and what's deliberately left unenforced (monitoring/API-key/
repo-connector limits exist in `Entitlements`' shape for Phase 8/9 to read,
not yet enforced — nothing exists yet to restrict).

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

Still ahead: a read-only repository connector (secret and dependency
scanning, scored separately from the live-site score, explicitly deferred
out of Phase 9 to its own future phase) and outbound alert webhooks (email
remains the only delivery channel) — see `docs/build-roadmap.md` for what's
next. All documents in `/docs` are authoritative for implementation and
must be updated by the responsible agent whenever behaviour changes.

## Licence

Apache 2.0. Automated assessments only — not legal advice and not a substitute for a
manual penetration test.
