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

## References

`docs/vision.md` §2, §5; `docs/prooflight-vision-and-architecture.md` §4;
`docs/modules.md` §2; `brand.config.json` (`namespaces.dnsVerificationKey`,
`namespaces.wellKnownPath`).
