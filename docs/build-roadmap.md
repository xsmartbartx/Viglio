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

## Phase 2 — Registry to v0.1 ✅

Filled out `SES` (6), `LEG` (4), `DEP` (4), `CMP` (4), `CLI` (10), `EXP` (5
— the passive subset only, see below), `DAT` (4) — 37 new checks, 57 total.
Three new probes: `wellknown_probe` (`.well-known` presence, passive per
`docs/vision.md`), `bundle_probe` (fetches linked `<script src>` content,
egress-guarded per script, same rule as the root page), `backend_probe`
(detects exposed Supabase/Firebase/S3/GCS credentials and makes one bounded,
egress-guarded reachability request per discovery — ADR-0003 addendum
records why this runs at passive tier). `EvidenceBundle` gained
`bundle`/`wellknown`/`backends` fields. Check-descriptor format unchanged
(`CheckManifest` already matched this shape from Phase 1).

**`EXP`'s full v0.1 scope (12 checks) is not all here.** Path/directory
enumeration, backup-file and debug-route detection require the Tier-1-only
`paths` probe (`docs/modules.md` §3) and verified ownership, which doesn't
exist until Phase 3 — see the ADR-0003 addendum. The 5 checks here (four
`.well-known` presence checks plus homepage verbose-error detection) are
the genuinely passive subset; the other 7 move to Phase 6.

**Done when:** every check has fixtures (pass/fail/inconclusive, inline in
its test file) and a primary-standard reference — confirmed for all 57;
`docs/check-catalog.md` generated from the descriptors via
`scripts/generate_check_catalog.py`; the backend probe's SSRF safety suite
(`packages/probes/tests/test_backend_probe_ssrf.py`) is green and
build-blocking, same standard as Phase 0's egress-guard suite; the golden
fixtures demonstrate the full registry (`good-config.json` scores 100/A,
`bad-config.json` scores 0/F including `VG-DAT-001`, the flagship exposed
service-role-key check, end to end).

**Running total: 57 of the ~64-check v0.1 target** — the remaining 7 are the
active-tier `EXP` checks deferred to Phase 6 below.

## Phase 3 — Control plane ✅

`apps/api` grew real endpoints (`/v1/scans`, `/v1/targets`, `/v1/me` —
`docs/api.md`); PostgreSQL + SQLAlchemy 2.0 (async) + Alembic, via a new
`packages/persistence` package; new `packages/identity` (Accounts, Clerk
mapping) and `packages/project` (Projects, Targets, OwnershipProofs)
modules (`docs/modules.md` §2a/§2b); `resolve_authorization()` and
`verify_ownership()` implemented in `packages/security` per ADR-0003
(fail-closed, audit-trail-first, both build-blocking-tested); a real
`packages/orchestrator` (state machine + ARQ task bodies, replacing
`packages/probes`' Phase-1 CLI-only convenience wrapper); a new
`packages/integrations` (Postmark email, MinIO/S3 object storage); a new
`apps/scanner` app running the ARQ worker — the only process that imports
`vigilo_probes` from the control-plane side, enforced by
`apps/api/tests/test_no_egress_imports.py`. Clerk chosen for managed auth,
Postmark for transactional email (both recorded in the ADR-0003 Phase 3
addendum alongside the append-only-trigger decision).

**Done when:** an unauthenticated visitor can scan a public site and receive
a report by email, and a target owner can complete DNS/file/meta-tag
verification and see their target upgrade to the active tier. Verified: the
anonymous scan path (`POST /v1/scans` → `resolve_authorization` →
`ScanJob` → ARQ `run_scan_job` → probes → checks → scoring → object
storage → Postmark) and the ownership-verification path (`POST
/v1/targets` → `POST .../verification` → place the DNS/file/meta-tag
record → `POST .../check` → ARQ `verify_ownership_job` →
`Target.verification_status` flips to `active`) both run end to end
locally against real Postgres/Redis/MinIO, with the append-only audit
trigger and both build-blocking network-safety suites
(`egress-guard-suite`, `ownership-verification-suite`) green in CI.

## Phase 4 — Report experience ✅

Web report UI (`apps/web`, Next.js 16 + Clerk), evidence panels (per-finding
`matched_indicator`/`request_summary`, a schema gap fixed this phase — see
`docs/data-model.md`'s `findings` table), severity grouping, skipped-checks
transparency (`INCONCLUSIVE`/`NOT_APPLICABLE` render as two distinct,
explicitly-labelled sections, never silently merged into "passed" — per the
Phase 0 domain model's `Verdict`), PDF export via a real headless-browser
(Playwright) render of the same live HTML page — one layout source of
truth, not a parallel server-templated system. The real `packages/reporting`
package landed this phase too (deterministic-only: static
`remediation_template` text, no LLM yet — Phase 5 swaps one function's
internals without changing the call site). The full `ShareLink` entity
(hashed, expiring, revocable tokens with view counts) shipped additively on
top of Phase 3's no-login unguessable-scan-UUID access, not as a
replacement for it.

**Done when:** a non-technical reader can act on a report without asking a
clarifying question first. Verified live, end to end, against a real scan of
`https://example.com` (Postgres/Redis/MinIO + `apps/api` + `apps/scanner` +
`apps/web`, a throwaway Clerk dev instance provisioned via `npx clerk@latest
init`): `/reports/{scanId}` renders score, severity-grouped findings,
remediation text, and both skipped-checks sections (`COULDN'T CHECK`/`NOT
APPLICABLE` render as distinct, itemised sections, never merged into
"passed"); PDF export round-trips through a real Chromium render of the same
live page (`?print=1` hides header chrome and force-expands every evidence
panel and the passed/skipped sections, so the PDF is a complete standalone
document); a share link created directly against the `reports` repository
resolves publicly through both `GET /v1/share/{token}` and `/share/{token}`,
increments `view_count`, and returns `410 SHARE_LINK_REVOKED` on the next
resolution after revocation. **This pass caught and fixed a real bug**:
`render_report_pdf_job` was passing the `Report` row's own id to
`render_pdf()`, which expects the *scan's* public job id — the PDF silently
rendered `apps/web`'s 404 page instead of the report (no exception, just a
one-page PDF of "not found"); fixed by resolving `Scan.job_id` first
(`packages/orchestrator/src/vigilo_orchestrator/jobs.py`), and the
regression test now asserts the exact id `render_pdf` receives, not just
that it was called.

**Known verification gap:** the full Clerk-authenticated browser flow (sign
in → owner-only PDF/share-link controls appear → create/revoke through the
actual UI) was not driven end to end — Clerk's hosted sign-up throws a
Cloudflare Turnstile bot-check that this project will not attempt to solve
or bypass by design. Clerk wiring itself (JWKS verification, the
`vigilo-api` JWT template's `email` claim) is confirmed working up to that
point, and `require_account`/`optional_account`/ownership-tracing logic has
its own unit coverage (`apps/api/tests/test_reports.py`,
`test_share_links.py`); a human still needs to click through the real
sign-in once. `uv run pytest -q` (361 tests) and `uv run ruff check .`
(Python), `npm run lint`/`npm run build` (`apps/web`) all green, including a
new `web` CI job.

## Phase 5 — Analysis layer (LLM) ✅

Claude-backed, structured per-finding remediation
(`explanation`/`impact`/`remediation_steps`/`agent_prompt`/
`estimated_effort` — `docs/prooflight-vision-and-architecture.md` §9.3's
exact shape), strictly additive per `docs/adr/ADR-0004-llm-boundary.md`
(replacing a stale "ADR-0001 rule 2" citation this paragraph used to carry —
checked, and that rule is the unrelated probe/check separation) — it
attaches prose to findings that already exist and never creates, deletes,
reclassifies or re-ranks one, never sets a score/grade/severity/verdict.
Redaction is allowlist-based (`finding.title`/`summary`/`severity`,
`manifest.description`/`category`, `finding.evidence.matched_indicator` if
present — never `target_origin`, never the raw evidence bundle), the LLM's
JSON response is strictly schema-validated and discarded whole on any
failure, and generation happens in a new background job
(`generate_remediations_job`, `packages/orchestrator`) auto-enqueued right
after scan scoring — never inline in `run_scan_job`, so a report render
never awaits or depends on the LLM. Results cache by `(fingerprint,
registry_version)` (a new `remediation_cache` table), so a repeat scan of
the same target skips the LLM entirely on a cache hit — the cost mitigation
the Prooflight doc's own risk register calls for. `apps/web`'s `FindingCard`
now surfaces the structured output, including a dedicated, copy-to-clipboard
`agent_prompt` block — the README's headline "paste-ready fix for every
finding" promise, built for real this phase rather than implied by generic
template text.

**Done when:** the LLM provider can be switched off entirely and the product
still ships a complete report from static remediation templates. Verified
live, not just unit tested: a real scan of `https://example.com` with
`ANTHROPIC_API_KEY` unset completed normally, `generate_remediations_job`
ran (confirmed in worker logs) and completed in milliseconds (no network
call attempted), every one of the 11 failed findings' report JSON showed
`remediation.source: "template"`, `apps/web`'s report page rendered the new
structured layout correctly (explanation, impact, ordered steps, and 11
distinct "Paste into your AI coding tool" blocks, one per failed finding),
and a direct `render_pdf()` call produced a 6-page PDF with every
`agent_prompt`'s text present and the interactive Copy button chrome absent
(`printMode` correctly gates only the button, never the content). `uv run
pytest -q` (388 tests, 27 new this phase) and `uv run ruff check .` both
green.

**Known verification gap:** the actual Claude-generated path (a real
`ANTHROPIC_API_KEY` producing valid structured JSON, `cache_remediation()`
persisting it, a repeat scan hitting that cache) was not driven live — the
user was asked and declined to share a real API key for this one test.
Unit coverage stands in for it instead: `packages/reporting/tests/
test_remediation.py` exercises `generate_remediation()` against a fake
`llm_caller` for the valid-response, malformed-JSON, missing-field,
invalid-`estimated_effort`, and caller-raises cases;
`packages/integrations/tests/test_llm.py` exercises the actual HTTP
request/response handling against `httpx.MockTransport` (well-formed
response, multi-block response, a 4xx rejection, a transport error, an
empty-content response); `packages/orchestrator/tests/test_remediation.py`
proves the cache round-trips an LLM result, silently skips a template
result, and correctly keys on the composite `(fingerprint,
registry_version)`. A human with a real Anthropic key can complete this
gap at any time by setting `ANTHROPIC_API_KEY` and re-running the scan
above — nothing else changes.

## Phase 6 — Active tier (scoped) ✅

Scoped down from the original paragraph, by explicit decision: `APP`
(application logic)/`AUT` (authentication surface)/`INF`
(infrastructure/DNS) are deferred to their own dedicated follow-up phase —
unlike everything else below, they have no concrete check list or probe
design anywhere in the docs, only one-line category descriptions
(`docs/adr/ADR-0003-scan-authorization-model.md`'s Phase 6 addendum has the
full reasoning). What shipped:

**Two-layer tier-gating enforcement** — the phase's actual exit criterion,
and a real, previously-undocumented gap: no code anywhere filtered which
checks ran by `tier_required` against a scan's granted tier; every check
ran unconditionally regardless of verification status. Fixed at both the
probe layer (`run_probes(url, tier=Tier.PASSIVE, ...)` only fires the new
`paths` probe's requests at `Tier.ACTIVE` — an unverified target must never
even receive the hidden-path-enumeration requests, not just have the
resulting findings filtered out) and the check layer (`plan_registry()`,
`packages/checks`). A new build-blocking CI suite (`tier-gating-suite`)
proves both directions — a passive job never produces an active finding,
an active job does — so the guarantee can't pass vacuously.

**The `paths` probe + the 7 `EXP` checks deferred from Phase 2**
(`VG-EXP-006`..`012`: repository metadata, backup artefacts, exposed
configuration, debug routes, test/staging routes, directory listing,
default admin panels) — Tier 1 only, a small fixed candidate-path list
(~29 paths total), per ADR-0003. `DAT` (data-platform posture) already
shipped at passive tier in Phase 2 — see that same ADR's earlier addendum
for why.

**`budget_cost` as a descriptor field**, not the full dynamic request-budget
planner (§8.5 of the Prooflight doc) the original paragraph named — that
needs a `skipped` verdict state that doesn't exist yet, and nothing in the
current registry comes close to the suggested ceilings for it to matter.
Explicitly deferred, not silently dropped — see the ADR-0003 Phase 6
addendum.

**A second, independent gap fixed in the same phase**: `apps/api`'s
`submit_scan()` was hardcoding `Tier.PASSIVE`/`False` into every
authorization check, so no scan could ever actually be granted active tier
— unrelated to the gating work above, but it would have shipped that work
provably correct and practically inert. Fixed via a new read-only
`get_account_by_email()` lookup for returning submitters only.

Registry: 57 → 64 checks.

**Done when:** it is proven by test — not just by code review — that no
active-tier check is reachable against an unverified target under any code
path. Verified live against a real scan of `https://example.com`: a
new-origin submission still grants `passive` and its report carries exactly
57 findings, none of `VG-EXP-006`..`012`. A target with a real, verified
DNS-TXT ownership proof (seeded via `vigilo_project.repository`'s existing,
already-tested functions — `create_target`/`issue_ownership_proof`/
`mark_proof_verified` — rather than driving Clerk's hosted sign-in UI,
which hits a Cloudflare bot-check this project won't attempt to solve, the
same limitation noted in Phases 4/5) resubmitted through the real
`POST /v1/scans` HTTP endpoint with `requested_tier: active` was granted
`granted_tier: "active"` — for the first time anywhere in the product — and
its report carries all 64 findings, `VG-EXP-006`..`012` included (all
`passed`, correctly, against a clean target). The active-tier job also took
visibly longer end to end (3.58s vs. 1.38s for the passive job, in worker
logs) — consistent with the `paths` probe's ~29 additional bounded requests
actually firing only in the active case. `uv run pytest -q` (413 tests) and
`uv run ruff check .` both green, including the new `tier-gating-suite`
CI job.

## Phase 7 — Monetisation (scoped) ✅

Scoped down from the original paragraph, by three explicit decisions
(`docs/adr/ADR-0002-product-scope-and-stack.md` names Paddle first among
merchant-of-record candidates, so it's the concrete reference
implementation here — Lemon Squeezy remains a same-shape alternative, not
built): (1) build the full entitlement architecture and the
checkout/webhook adapter now, but **stubbed** — no real Paddle account;
verified against a locally-computed, validly-signed mock webhook payload,
the same DI-seam pattern already used for Postmark/Clerk/Anthropic; (2)
**enforce only what exists today** — target count, scans/month,
passive-vs-active tier, share-link export. `Entitlements` already carries
`monitoring_frequency`/`api_keys_limit`/`repo_connectors_limit` fields
(Phase 8/9-shaped) so those phases have a snapshot to read, but nothing
enforces or tests them yet, since no monitor, API key, or repo connector
exists to restrict; (3) legal pages are real, clearly-labeled **drafts** —
covering Vigilo's actual authorization model, data handling and abuse
policy, not Lorem Ipsum — with a persistent "DRAFT — not reviewed by a
lawyer" banner, not a claim of legal review. What shipped:

**`packages/billing`** — pure entitlement logic (`entitlements()`,
`consume()`, `interpret_webhook_event()`), `core`-only, zero ORM, matching
the precedent `resolve_authorization`/`build_report` already set
(`docs/modules.md` §11's deviation note has the detail). Three static
plans (Free/Builder/Studio) at `TARGETS`/`SCANS_MONTHLY` meters, both
enforced as a live `COUNT`, never a stored/decremented counter — nothing to
drift out of sync. `Subscription` persistence lives in `packages/identity`
next to `Account`, not a `billing`-owned table.

**A real, previously-latent quota bypass, found and fixed in the same
phase** (not a Phase 7 regression — a gap that predates this phase but had
no quota to bypass until now): `submit_scan()`
(`apps/api/src/vigilo_api/routers/scans.py`) auto-creates a `Target` row
for any new origin a returning account scans, entirely independent of
`POST /v1/targets`' own quota check. Both paths now enforce the same
`TARGETS` check.

**Checkout + webhook routes** (`apps/api/src/vigilo_api/routers/billing.py`)
— `POST /v1/billing/checkout` builds Paddle's hosted-checkout URL;
`POST /v1/billing/webhook` is deliberately public (Paddle authenticates via
HMAC signature, not a bearer token), applies a recognized, correctly-signed
event via `upsert_subscription()`, and returns `200`/no-op for anything
else — see `docs/security.md` §7 for the attack-surface writeup, including
the disclosed, not-yet-closed replay-protection gap.

**Legal pages + footer** (`apps/web/app/{privacy,terms,cookies,aup}/page.tsx`,
`components/{DraftBanner,Footer}.tsx`) — real drafted text, footer wired
into the homepage. Verified two ways: `packages/checks`' actual
`Check.evaluate()` functions run against the live-fetched homepage HTML
confirm all four passive `LEG` checks pass (`VG-LEG-001`..`004`); the
`CMP` checks pass vacuously, since the homepage sets no trackers to flag.
A full `vigilo scan` of the running local dev server wasn't possible —
`localhost` is loopback, which the egress guard denies by design (SSRF
protection, `docs/security.md` §1) — running the real check functions
against the real fetched content is the closest available proxy, and is
what those checks actually evaluate internally regardless of how the fetch
happened.

**The regression this phase itself would have introduced, and its fix**:
Phase 6's `test_submit_scan_grants_active_tier_for_a_returning_verified_target`
seeded an account with no plan (`plan_id=None`, defaulting to Free), which
Phase 7's new plan gate would have silently downgraded to passive despite a
valid, verified proof — the exact "accidental free active scan" the
Prooflight doc's risk register warns about. Fixed by upgrading that test's
account to `builder` before asserting active tier, and adding a new,
arguably more important test,
`test_submit_scan_with_valid_proof_but_free_plan_stays_passive` — the
concrete, testable analogue of this phase's own exit criterion below.

**Done when:** entitlements are enforced from exactly one call site
(`vigilo_billing.entitlements()`/`consume()`, never re-derived elsewhere),
and a plan change correctly and immediately restricts or unrestricts
access. Verified live, end to end, in
`apps/api/tests/test_billing.py::test_a_plan_upgrade_via_webhook_immediately_unlocks_active_tier`:
a verified-owner account on the default Free plan submits an active-tier
scan and is granted `passive`; a real `POST /v1/billing/webhook` call
(locally-computed valid signature, no real Paddle account) upgrades the
account to `builder`; the identical scan request is then granted `active`
— no other state changed between the two calls. The literal "restricts an
active monitor" wording in the original exit criterion is satisfied by this
test instead of a literal monitor test, since no monitor exists yet
(Phase 8) to restrict — the plan-gating mechanism itself is what that
wording was really testing for, and it's proven here against the one
plan-gated feature that does exist (active tier).

`uv run pytest -q` (462 tests) and `uv run ruff check .` both green,
including `packages/billing/tests/test_import_boundary.py`'s new
build-blocking `core`-only boundary check.

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
