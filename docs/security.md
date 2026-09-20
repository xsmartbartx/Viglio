# Security

## Purpose

Detail for the `security` module (`docs/modules.md` §2). This document grows
phase by phase alongside the code — it is not a complete security model yet.
Referenced by `docs/architecture.md` and ADR-0003.

**Phase 0** shipped the egress guard only. **Phase 3** adds scan
authorization, ownership verification and the audit-trail writer (§3-§5
below) — the rate governor and abuse heuristics remain future work (§2).
**Phase 5** adds the LLM prompt boundary (§6) — the first place an
untrusted, target-controlled string reaches a third-party model. Redaction
(`redact()`) is implemented in `packages/core`, not here, since it has no
I/O and no security *decision* to make — see `docs/modules.md` §1. **Phase 9**
adds the public API's Redis-backed rate limiter and the API key storage
model (§9) — a first, narrower-than-originally-described implementation of
§2's long-open rate-governor entry.

---

## 1. Egress guard (SSRF / DNS-rebinding defense)

**Status: implemented, `packages/security/src/vigilo_security/egress_guard.py`.**

A scanner takes a user-supplied URL and fetches it. That is SSRF as a
product feature, not a bug to patch around — so it's the first thing built,
and the only thing in this module that's build-blocking in CI today.

### What it does

`validate_and_pin(url, resolver=None) -> ValidatedConnection`:

1. Validates URL grammar via `vigilo_core.validation.validate_target_url`
   (http/https only, no userinfo, no fragment, port from `{80, 443, 8080,
   8443}`, length ≤ 255, rejects raw-IP-literal hosts).
2. Resolves DNS — `socket.getaddrinfo` by default, but every caller in tests
   injects a fake resolver, so CI never performs a real DNS lookup or
   connects to a real host (see `docs/architecture.md` §11: "No live
   third-party targets in CI, ever").
3. Classifies **every** resolved address (not just the first) against the
   denied set: loopback, unspecified, link-local (this is what blocks the
   `169.254.169.254` cloud-metadata endpoint — the single most damaging SSRF
   outcome), CGNAT (`100.64.0.0/10`, checked explicitly since Python's
   `ipaddress.is_private` doesn't flag it), multicast, reserved, RFC1918
   private, and IPv4-mapped IPv6 wrapping any of the above.
4. Returns the literal resolved IP as the "pin." The caller (Phase 1's probe
   HTTP client) must connect to that literal address, never re-resolving
   between check and connect — that's what defeats DNS rebinding.

`revalidate_redirect()` re-runs the same check for a redirect hop. **Not yet
implemented:** restricting redirects to the same registrable domain, so a
target can't use a redirect to point the scanner at an unrelated third party.
That needs a public-suffix-list dependency and is deferred to Phase 1.

### Testing

`packages/security/tests/test_egress_guard.py` is the suite
`docs/prooflight-vision-and-architecture.md` §18.3 calls "any pass is a
build-blocking failure" — it runs as its own named CI job
(`egress-guard-suite`, `.github/workflows/ci.yml`) so the gate is visible
independent of the rest of the test run. It exercises every denied class
above via a fake resolver, plus a DNS-resolution-failure case (denied, not
silently skipped), a mixed-results case (one safe address, one unsafe — must
still deny), and a redirect-into-internal-space case.

---

## 2. Not yet implemented (tracked so it isn't forgotten)

| Concern | Where it will live | Blocked on |
| --- | --- | --- |
| Abuse heuristics (enumeration patterns, target churn) | `packages/security` | Scan history to detect patterns against (Phase 3+) |
| Redirect same-registrable-domain restriction | `packages/security/egress_guard.py` | Public-suffix-list dependency (Phase 1) |
| Worker network isolation (the scan zone has no route to internal services) | Deployment topology, not application code | Phase 1 deployment target |
| Automated `/.well-known/vigilo-optout.txt` denylist fetching | `packages/security`/`packages/project` | Phase 3 scope trim — `Target.opt_out_flag` exists with a manual setter only |
| Email ownership verification | `packages/security/ownership.py` | A click-through confirmation UI (Phase 4) |

---

## 3. Scan authorization (`resolve_authorization`)

**Status: implemented, `packages/security/src/vigilo_security/authorization.py`.**

A pure function over primitives and enums — `AuthorizationRequest` in,
`AuthorizationDecision` out — with no ORM types and no I/O, matching
`security`'s dependency-graph position (`core` + `persistence` only, never
`identity`/`project`). The caller (an `apps/api` handler) is responsible for
loading whatever `Account`/`Target`/`OwnershipProof` state it needs and
reducing it to `AuthorizationRequest`'s fields before calling this.

**Decision order** (first match wins, fail-closed throughout):

1. `denylisted` or `target_opt_out` → **deny outright**. No scan, no
   `Account`/`Target` row created — only the audit event.
2. `recent_scan_count_24h` over a fixed ceiling (20, a Phase 3 scope trim —
   the full Redis-backed governor is Phase 6/7, and is a *different*
   concern from this one: §9's public-API rate limiter is per-account
   request throughput, this is per-target scan volume) → **deny**, code
   `RATE_LIMIT_EXCEEDED`. **Implemented and live** (post-Phase-9 gap
   closure) — `count_scan_jobs_for_target_since()`
   (`packages/orchestrator/src/vigilo_orchestrator/service.py`) feeds a
   real, per-target rolling-24h count from all three callers
   (`apps/api`'s `submit_scan()`/`public_submit_scan()`, and
   `apps/scanner`'s scheduled-monitor re-authorization). Scoped
   per-target, not per-account or global — the narrowest of the three
   candidates this row's table entry used to list side by side, matching
   `detect_regression()`'s identical per-target precedent
   (`list_ever_failed_fingerprints_before()`). A brand-new target's count
   is `0` (nothing to count yet, not a loophole — the very first scan of
   a target can never be denied by this ceiling).
3. `requested_tier == ACTIVE` without both `target_verification_status ==
   ACTIVE` *and* `ownership_proof_valid` → **downgrade to passive, not a
   rejection**. ADR-0003 says tier resolution "never upgrades" — a request
   for more than is available is granted at what *is* available, which is
   a downgrade, not a failure.
4. Otherwise → allowed at the requested tier.

Every branch is exercised in `packages/security/tests/test_authorization.py`,
including that a denylist hit overrides even a fully verified, valid proof.

## 4. Ownership verification (`verify_ownership`)

**Status: implemented, `packages/security/src/vigilo_security/ownership.py`.**

Four methods, matching ADR-0003's ownership-proof list:

| Method | How | Touches the target? |
| --- | --- | --- |
| `dns_txt` | Injectable TXT-record resolver (`dnspython`), looks for `<dnsVerificationKey>=<nonce>` | No — queries DNS infrastructure, not the target |
| `wellknown_file` | `validate_and_pin()` then a bounded GET on `<wellKnownPath>`, exact-match the nonce | Yes |
| `meta_tag` | `validate_and_pin()` then a bounded GET on `/`, regex for `<meta name="...verification" content="...">` | Yes |
| `email` | Not implemented — `NotImplementedError` | N/A |

The two target-fetching methods are built on the **exact `validate_and_pin`
template** the egress guard established: dependency-injected resolver/
transport, a dedicated result shape, deny-by-default. They call
`validate_and_pin()` and connect to the pinned IP before any request, same
as any probe — this is SSRF-relevant code by construction, not by
afterthought.

**Where this runs.** Always dispatched via `verify_ownership_job` inside
`apps/scanner`'s ARQ worker — never called synchronously from `apps/api`,
for all four methods, including the two (`dns_txt`, `email`) that don't
fetch the target directly. See the ADR-0003 Phase 3 addendum for the
reasoning: uniformity with "the control plane never makes an outbound
request to a target, ever" beats a method-by-method special case.

**Testing.** `packages/security/tests/test_ownership.py` is build-blocking
in CI (`ownership-verification-suite`, `.github/workflows/ci.yml`), same
standard as the egress-guard suite: no real DNS or network I/O anywhere in
that file, proven by construction (every call passes an explicit
`resolver=`/`txt_resolver=`/`transport=`), plus an explicit parametrized
check that a target resolving to loopback/link-local/metadata addresses is
denied before any HTTP request is attempted.

## 5. Audit trail (`audit`)

**Status: implemented, `packages/security/src/vigilo_security/audit.py`
+ `orm.py`.**

`audit(session, event: AuditEvent) -> None` takes an already-open session
so a caller can make "resolve authorization → write the audit event →
create the ScanJob" one transaction, committed together — the literal
ordering ADR-0003 requires ("written to the audit trail before the scan is
queued, not after").

**Append-only is a database property**, not application discipline:
`packages/persistence/migrations/versions/0002_audit_events_append_only.py`
adds a Postgres `BEFORE UPDATE OR DELETE OR TRUNCATE` trigger on
`audit_events` that unconditionally raises. A trigger, not a `REVOKE`
grant, because the database has one owning role and Postgres owners bypass
`REVOKE` — see the ADR-0003 addendum for the full reasoning.
`packages/security/tests/test_audit_append_only.py` runs the real
migrations (not the ORM-only `Base.metadata.create_all()` other tests use)
and proves `UPDATE`, `DELETE`, and `TRUNCATE` all raise.

## 6. LLM prompt boundary (`generate_remediation`)

**Status: implemented, `packages/reporting/src/vigilo_reporting/remediation.py`.**
Full decision record: `docs/adr/ADR-0004-llm-boundary.md`. Summarized here
because it's a real, if partial, mitigation for a genuine untrusted-input
surface, matching this document's scope.

**The attack surface.** A finding's `summary`/`title`/`evidence.
matched_indicator` ultimately derive from a real HTTP response the
*scanned target* controls — not a trusted first-party source. That content
is embedded in a prompt sent to Claude, and the model's `agent_prompt`
output is explicitly meant to be pasted into a user's own AI coding tool —
a real downstream execution context. A malicious or compromised target
could in principle craft response content designed to hijack the
remediation prompt.

**Mitigation, and its limits.** Two structural backstops, neither a
complete defense: (1) the prompt-construction call site only reads from an
explicit allowlist of fields (`finding.title`/`summary`/`severity`,
`manifest.description`/`category`, `finding.evidence.matched_indicator`)
and never sends `target_origin` or the raw evidence bundle; (2) the
model's response is required to be strict JSON matching `RemediationPrompt`'s
schema, and any parse or validation failure discards the response whole and
falls back to the static template — never partially parsed. Neither stops
a sufficiently crafted payload that still produces well-formed JSON with
poisoned field values. Recorded as a known, deliberately-scoped gap, not
claimed as solved — revisit if it manifests as a real incident.

**What's deliberately out of scope.** §9.2 step 4 of
`docs/prooflight-vision-and-architecture.md` suggests tokenizing the target
domain for EU-boundary data-residency reasons. No data-residency
infrastructure exists yet (`accounts.data_region` is an unused placeholder,
`docs/data-model.md`), so this phase omits `target_origin` from the prompt
entirely instead — stronger than tokenizing it, and needs no new
infrastructure.

## 7. Billing webhook (`POST /v1/billing/webhook`)

**Status: implemented, `apps/api/src/vigilo_api/routers/billing.py` +
`packages/integrations/src/vigilo_integrations/billing.py`.**

**The attack surface.** This route is deliberately public — a merchant of
record (Paddle) calls it from outside our network, so it cannot require the
bearer token every other mutating route requires. Signature verification
(`verify_webhook_signature()`, HMAC-SHA256 over `Paddle-Signature`'s
`ts:body` per Paddle's documented scheme) is the *only* gate: an invalid or
missing signature is rejected with `401` before the body is ever parsed as
JSON, let alone interpreted as a subscription event.

**What a forged event could do if the gate failed.** `interpret_webhook_event()`
maps a recognized event straight to `upsert_subscription()`, which cascades
`accounts.plan_id` — a forged, correctly-signed "subscription.created" event
for an arbitrary `account_email` would grant that account a paid plan's
entitlements for free. This is why the signature check happens first, over
the raw, unparsed bytes, and why the webhook secret
(`PADDLE_WEBHOOK_SECRET`) is treated with the same care as the other
optional-but-sensitive provider secrets in `.env.example`.

**Deliberately not implemented: replay protection.** The signature covers a
timestamp (`ts=`) but this implementation does not currently reject a
signature whose timestamp is old — a captured, validly-signed request could
in principle be replayed. `upsert_subscription()`'s own idempotency
(keyed on `provider_subscription_id`) limits the damage of a naive replay to
a no-op re-application of the same, already-applied state, not a fresh
unauthorized change — but a genuine replay window still exists. Tracked as
a known gap, not fixed this phase, matching this document's convention of
disclosing rather than silently deferring.

**Unrecognized events return `200`, not an error.** An unrecognized
`event_type` or a recognized type with a malformed payload is a no-op that
still returns `200` — matching Paddle's own expected webhook behavior and
avoiding a retry storm from a provider event this integration doesn't act
on. This is a deliberate availability trade-off, not a validation gap: the
signature check has already run by this point, so an attacker cannot use
this path to probe for accepted event shapes without a valid signature.

## 8. Monitoring — scheduled re-authorization and the public badge route

**Status: implemented, `packages/monitoring`, `apps/scanner/src/
vigilo_scanner/jobs.py`, `apps/api/src/vigilo_api/routers/{monitors,badge}.py`.**

**Scheduled scans reuse the exact same authorization path.** A monitor
never bypasses `resolve_authorization()` — `check_due_monitors_job`
always requests active tier and lets the same function `submit_scan()`
calls downgrade it, re-verifying `has_valid_ownership_proof()` on every
cycle. This is what makes "ownership revocation immediately downgrades all
future scheduled scans" (§3's authorization-order guarantee, extended)
true in practice, not just in principle: there is no separate,
monitor-specific authorization code path that could drift out of sync
with the one HTTP submission uses.

**`GET /badge/{target_id}.svg` is deliberately public** — meant to be
embedded cross-origin via a plain `<img>` tag on the target owner's own
site, the same posture `GET /v1/scans/{id}/report` already established
("an unguessable UUID is already a de facto share link," §7 of
`docs/architecture.md`). It leaks no finding data **by construction**, not
by a filter that could be forgotten: `render_badge()`
(`packages/reporting/src/vigilo_reporting/badge.py`) takes only a `Score`
and a timestamp as arguments — there is no code path by which a finding
title, check id, or evidence string could reach the SVG it returns.

**Alert emails never carry evidence.** `packages/notification`'s
templates render only `event_type`/`check_id`/`severity` — the same
allowlist discipline §6 established for the LLM remediation prompt boundary,
applied here to outbound email instead of an outbound model call. Every
alert links to the monitoring dashboard (an authenticated page), never
directly to a finding's evidence panel.

---

## 9. Public API rate limiting and API key storage (Phase 9)

**Status: implemented, `packages/security/src/vigilo_security/rate_limit.py`,
`apps/api/src/vigilo_api/api_key_auth.py`, `packages/identity`.**

**Rate limiting.** `check_rate(redis, key, limit, window_seconds=60)` is a
Redis `INCR`+`EXPIRE` fixed-window counter — closes §2's long-open
"Redis-backed rate governor" entry, but **scoped to the key-authenticated
public API only** (`/public/v1/*`), not §3's authorization-time ceiling or
a per-target-host/global limit; see §2's row above for exactly what
remains open. `require_scope()` (`api_key_auth.py`) calls it keyed by
`f"ratelimit:{account.id}"` — one shared budget per **account**, not per
individual key, per `entitlements(plan_id).api_rate_limit_per_minute`
(Free has no key access at all, so no limit applies; paid tiers range
60-1000/minute, `docs/modules.md` §11). `limit=None` always allows,
matching `vigilo_billing.consume()`'s own "`None` means unlimited"
convention rather than inventing a second one. A denial returns `429` with
a `Retry-After` header (`decision.retry_after_seconds`), letting a
well-behaved client back off without guessing.

**API key storage.** An API key's plaintext (`f"vglo_{secrets.token_urlsafe(32)}"`,
~256 bits of entropy) is returned exactly once, at creation
(`POST /v1/me/api-keys`), and never persisted or logged — only
`sha256(plaintext).hexdigest()` is (`api_keys.key_hash`,
`docs/data-model.md`), the same hash-only-at-rest posture `share_links`
already established for its own bearer token, and for the same reason:
the token already carries enough entropy that a slow KDF would add cost
without adding real resistance. `hash_api_key()` is the single
implementation both key creation and `require_api_key()`'s lookup call, so
there is exactly one place this hashing logic could drift. `ApiKey`'s
Pydantic response model (`packages/identity/src/vigilo_identity/models.py`)
omits `key_hash` entirely — a `model_validate()` call against the ORM row
structurally cannot leak it, not merely a serializer that remembers to
exclude it.

## References

ADR-0001, ADR-0002, ADR-0003 (including its Phase 3 addendum), ADR-0004,
`docs/architecture.md` §7 and §15 (numbered as such in
`docs/prooflight-vision-and-architecture.md`), `docs/modules.md` §2, §2a, §2b,
§9, §10, §11, §12, §13, `docs/data-model.md`, `docs/api.md`'s public API
section.
