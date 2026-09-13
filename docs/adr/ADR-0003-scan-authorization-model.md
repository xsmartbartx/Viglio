# ADR-0003: Scan authorization model

| Field | Value |
| --- | --- |
| Status | Accepted (model); implementation deferred to Phase 3 |
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

## References

`docs/vision.md` §2, §5, §7; `docs/prooflight-vision-and-architecture.md` §4;
`docs/modules.md` §2, §3; `brand.config.json` (`namespaces.dnsVerificationKey`,
`namespaces.wellKnownPath`); `docs/build-roadmap.md` Phase 2 and Phase 6.
