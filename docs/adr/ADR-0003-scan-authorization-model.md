# ADR-0003: Scan authorization model

| Field | Value |
| --- | --- |
| Status | Accepted; implemented (Phase 3) — see the Phase 3 and Phase 6 addenda below |
| Date | 2026-09-11 |

## Context

Vigilo's core feature — fetching a user-supplied URL — is also, definitionally,
SSRF and unauthorized-scanning risk. `docs/vision.md` and
`docs/prooflight-vision-and-architecture.md` §4 already describe a two-tier
authorization model. This ADR records it as binding before any authorization
code is written, per `docs/modules.md` §2's "fail-closed" requirement.

## Decision

Two scan tiers, gated by different evidence:

| Tier | Requires | Permitted activity |
| --- | --- | --- |
| **Passive** (Tier 0) | Nothing beyond submitting the target | Requests a normal browser visiting the homepage would make: the homepage and its linked assets, `GET` on public `.well-known` paths, TLS handshake, DNS lookups, published legal pages. Read-only, no hidden-path enumeration, no parameter manipulation. |
| **Active** (Tier 1) | Verified ownership proof | Everything passive, plus non-linked-path probing, parameter manipulation on redirect targets, CORS preflight variations, bounded auth-endpoint throttling tests, subdomain enumeration. |

Ownership proof methods (any one sufficient; all recorded with timestamp and
method):

1. DNS `TXT` record containing a per-target nonce (`vigilo-site-verification`
   key, per `brand.config.json`).
2. A file at the published well-known path
   (`/.well-known/vigilo-verification.txt`, per `brand.config.json`).
3. A `<meta>` tag with the nonce on the site root.
4. Verified control of an email address at the target's registered domain.

Proofs expire (90 days) and re-verify silently before every scheduled active
scan; a lapsed proof downgrades future scheduled scans to passive rather than
failing them outright.

**Fail-closed is binding**: any error during tier resolution downgrades to
`passive` or rejects the scan outright. It never upgrades. Every
authorization decision — allow or deny — is written to an append-only audit
trail *before* the scan is queued, not after.

**Never in scope, at any tier**: destructive requests, credential guessing,
payload fuzzing (detection-only signatures — a reflected value proves the
finding; no shells, no `DROP`, no stored XSS), targets on internal address
space (enforced independently by the egress guard, `packages/security`, ADR
implied by `docs/architecture.md` §15.1 — belt and suspenders, not
either/or), or targets on the denylist (government, healthcare, financial
infrastructure, or any domain that has filed an opt-out via
`/.well-known/vigilo-optout.txt`).

## What Phase 0 implements vs. defers

Phase 0 ships the **egress guard** (`packages/security.egress_guard`) —
independent, target-address-level SSRF defense that applies regardless of
authorization tier. It does **not** implement `resolve_authorization()` or
`verify_ownership()`: those require `Account` and `Target` persistence
(database, DNS-lookup and file-fetch verification flows) that don't exist
until Phase 3 (Control plane). Building the authorization *decision* function
now, with nothing to authorize against, would be dead code exercising a
data model that doesn't exist yet.

## Consequences

- No active-tier check may become reachable in code before
  `resolve_authorization()` exists and is tested to fail closed. This is a
  standing constraint on every phase from here forward, not just Phase 3.
- The audit trail's append-only guarantee needs to be a database property
  (no UPDATE/DELETE grants on that table), decided concretely when Phase 3
  designs the schema — noted here so it isn't lost.

## Addendum (Phase 2): `EXP` tier split and `DAT`'s passive-tier classification

Two judgment calls made while filling out the check registry, recorded here
per the standing rule that authorization-model boundary decisions are
called out explicitly, not left implicit in a commit.

**`EXP` (surface exposure) is split across tiers.** The full v0.1 category
(12 checks) includes "browsable directories, backup artefacts, debug and
test routes, reachable configuration and repository metadata paths" — per
`docs/modules.md` §3, that is the `paths` probe, explicitly Tier 1 (active)
only. Shipping those checks against an unverified target would mean an
unauthenticated `vigilo scan` blindly enumerating hidden paths — a direct
violation of the passive-tier definition above ("no hidden-path
enumeration"). Phase 2 ships only the 5 checks derivable from data that is
already unambiguously passive: presence of the four `.well-known`-adjacent
files (`security.txt`, `robots.txt`, `sitemap.xml`, `manifest.json` — all
explicitly in-scope per the passive row above) and verbose-error detection
on the homepage response already fetched. The remaining 7 checks move to
Phase 6, alongside `APP`/`AUT`/`INF`.

**`DAT` (data platform posture — exposed Supabase/Firebase/S3/GCS
credentials) runs at passive tier**, including its live reachability probe
against a *dynamically discovered* second target. This is not obviously
"nothing beyond submitting the target" at first glance, so the reasoning is
worth stating: the probe uses the exact credential the site itself shipped
to every visitor's browser (an anon key, a public Realtime Database URL, a
public bucket URL found in a linked script) and issues one bounded,
read-only request to it — no guessing, no parameter manipulation on the
target's own application logic, nothing a normal page load wouldn't
eventually trigger via that same shipped credential. This is the same
reasoning that makes `.well-known` fetches and linked-asset fetches passive:
it's not enumeration, it's following what the target already handed out.
Per `docs/vision.md` §7, the free/passive scan is the acquisition mechanism
and must stay genuinely useful — gating the product's flagship check behind
Phase 3's ownership verification would defeat that. The discovered URL still
goes through `validate_and_pin` with zero exceptions
(`packages/probes/backend_probe.py`,
`packages/probes/tests/test_backend_probe_ssrf.py`) — passive tier changes
what's *permitted*, never what's *safe*.

## Addendum (Phase 3): implementation decisions

Three judgment calls made while actually building `resolve_authorization()`
and `verify_ownership()` — the functions this ADR named and deferred since
Phase 0 — recorded here per the same standing rule as the Phase 2 addendum.

**`verify_ownership()` always runs inside `apps/scanner`'s ARQ worker,
dispatched via `verify_ownership_job`, never called synchronously from
`apps/api` — for all four methods, not only the two that fetch the target.**
`docs/architecture.md` §3 is unconditional: "the control plane never makes
an outbound request to a target, ever." `dns_txt` queries DNS
infrastructure, not the target, and `email` (not yet implemented) would
send mail via Postmark, not touch the target either — a literal reading of
§3 wouldn't obviously forbid running those two synchronously in `apps/api`.
Uniformity was chosen anyway: one call path for all four methods is
simpler to reason about and audit than "these two are control-plane-safe,
these two aren't," and it costs nothing — an ARQ round-trip is already
how `apps/api` talks to everything scan-related. `POST
/v1/targets/{id}/verification/{proof_id}/check` therefore always enqueues
a job and returns `202`, never a synchronous verification result.

**Clerk was chosen over Supabase Auth** for the managed auth provider
`docs/adr/ADR-0002-product-scope-and-stack.md` left as an either/or,
deferred until an account model existed. Reasoning: this backend runs its
own Postgres (provisioned in Phase 0's `docker-compose.yml`), not
Supabase's, so Supabase Auth's main ecosystem synergy doesn't apply here;
Clerk has a clean, stateless JWKS-based JWT-verification story
(`apps/api/src/vigilo_api/auth.py`) with no vendor database lock-in, and
its hosted UI components pay off directly once Phase 4 builds the Next.js
frontend. `get_or_create_account()` (`packages/identity`) is the one
narrow seam a future provider swap would touch.

**The `audit_events` append-only guarantee is a Postgres `BEFORE UPDATE OR
DELETE OR TRUNCATE` trigger, not a `REVOKE` grant.** This ADR's Phase 0
Consequences section flagged the mechanism as "decided concretely when
Phase 3 designs the schema." A `REVOKE UPDATE, DELETE` grant only stops a
role that isn't the table's owner — the local/CI database has exactly one
role (`vigilo`), which owns every table it creates, and Postgres owners
bypass `REVOKE` unconditionally. Making `REVOKE` actually work would need
provisioning a second, non-owner database role and a second `DATABASE_URL`
across dev, CI and production — real infrastructure churn this phase
doesn't need. A trigger (`packages/persistence/migrations/versions/
0002_audit_events_append_only.py`) enforces the guarantee regardless of
which role runs the statement, including against `TRUNCATE` — found to be
a real gap during development, since Postgres row-level `BEFORE DELETE`
triggers do not fire for `TRUNCATE` at all, requiring a second,
statement-level trigger. Role-based `REVOKE` remains a reasonable
defense-in-depth addition for Phase 7 hardening, not a Phase 3 requirement.

## Addendum (Phase 6): tier-gating enforcement, and a real gap it exposed

`resolve_authorization()` has decided a scan's *granted tier* since Phase 3.
Nothing downstream ever acted on that decision until now — recorded here
because it's exactly the kind of authorization-model change standing rule
2 (`docs/build-roadmap.md`) requires an explicit callout for, even though
no line of `resolve_authorization()` itself changed.

**Tier-gating is enforced at two layers, not one, and both were missing.**
`run_registry()`/`to_findings()` (`packages/checks/src/vigilo_checks/findings.py`)
produce exactly one `Finding` per check passed in, regardless of verdict —
the existing `@requires("field")` decorator only demotes an unreachable
check to `INCONCLUSIVE`, it doesn't remove the `Finding` row. So check-layer
filtering (`plan_registry(registry, tier)`, new this phase) is necessary but
not sufficient on its own: a probe-layer gate is equally required, or the
real, SSRF-relevant HTTP requests (the new `paths` probe's hidden-path
enumeration) would still fire against an unverified target even if the
resulting evidence were discarded afterward. `run_probes(url, tier=
Tier.PASSIVE, ...)` (`packages/probes/src/vigilo_probes/orchestrator.py`)
only calls `run_paths()` at `Tier.ACTIVE`. Both gates default closed
(`Tier.PASSIVE`), so a caller that forgets to pass a tier explicitly — like
`apps/cli`, which has no ownership-verification mechanism at all — fails
safe. Proven by a dedicated, build-blocking CI suite
(`tier-gating-suite`, `packages/orchestrator/tests/test_tier_gating.py`),
same standard as the egress guard and ownership verification: both a
negative assertion (a passive-tier job never produces an active-tier
`Finding`, even when fed evidence that would trigger one) and a positive
one (an active-tier job does), so a bug that made gating unconditionally
closed can't pass the suite vacuously.

**A real, independent gap surfaced and was fixed in the same phase:**
`apps/api/src/vigilo_api/routers/scans.py`'s `submit_scan()` was calling
`resolve_authorization()` with `target_verification_status`/
`ownership_proof_valid` hardcoded to `Tier.PASSIVE`/`False` for every
request — never looking up a returning submitter's real, already-correctly-
tracked verification state (`vigilo_project.repository.get_target_by_origin()`/
`has_valid_ownership_proof()` already existed and worked, just weren't
called from here). This meant no scan could ever be granted active tier,
for anyone, verified or not — independent of and unrelated to the
tier-gating work above, but it would have made that work provably correct
and practically inert (a gate nothing could ever reach in the first place)
had it shipped unfixed. Fixed by a read-only lookup
(`vigilo_identity.repository.get_account_by_email()`, new) performed only
for a *returning* submitter — a brand-new submitter (no account yet) takes
exactly the prior code path, nothing read or created, preserving "a denied
scan may have no account yet" (`docs/data-model.md`'s `audit_events
.account_id` note) for the only case that invariant actually protects.
`target_opt_out`/`recent_scan_count_24h` remain separately hardcoded — both
already-documented Phase 3 scope trims (`docs/security.md` §2), not new
findings, not touched by this fix.

**Request-budget enforcement is deliberately not built this phase, despite
`docs/build-roadmap.md`'s Phase 6 paragraph naming it.** `CheckManifest`
gained a `budget_cost` descriptor field (default `0` — every check that
predates it costs nothing marginal, since checks are pure functions over an
already-fetched bundle; only the 7 new `paths`-dependent `EXP` checks set a
real value). The dynamic planner §8.5 of the Prooflight doc actually
describes — "drops the lowest-weight checks if the plan exceeds budget,
records them as `skipped:budget`" — needs a `skipped` verdict `Verdict`
doesn't have, and nothing in the current registry (57 passive + 7 active
checks, ~29 fixed `paths`-probe requests) comes close to the suggested
ceilings (60 passive / 220 active) for that engine to actually do anything
yet. A static test (`packages/checks/tests/test_findings.py`) proves the
registry's summed `budget_cost` stays within both ceilings today — "provable
by construction" for what exists, without runtime machinery that has
nothing to enforce.

**`APP`/`AUT`/`INF` (application logic, authentication surface,
infrastructure/DNS) are deferred to their own follow-up phase**, not built
alongside the above. Unlike the 7 deferred `EXP` checks (fully specified by
this ADR's Phase 2 addendum) or `paths`/`subdomain` (named and described in
`docs/modules.md` §3), these three categories have no concrete check list
or probe design anywhere in the documentation — only one-line category
descriptions in `docs/prooflight-vision-and-architecture.md` §7.2. Building
CORS-preflight testing, auth-endpoint throttling probes, redirect-parameter
fuzzing and subdomain enumeration from a one-line description each, rushed
alongside the well-specified work above, would mean designing real new
attack-surface probes without the deliberate reference-standard-plus-golden-
fixture rigor standing rule 1 requires for every other check in this
registry.

## References

`docs/vision.md` §2, §5, §7; `docs/prooflight-vision-and-architecture.md` §4,
§7.2, §8.5; `docs/modules.md` §2, §2a, §2b, §3, §4; `brand.config.json`
(`namespaces.dnsVerificationKey`, `namespaces.wellKnownPath`);
`docs/build-roadmap.md` Phase 2, Phase 3 and Phase 6; `docs/data-model.md`;
`docs/security.md` §2-§6.
