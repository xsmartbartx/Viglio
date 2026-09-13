# Security

## Purpose

Detail for the `security` module (`docs/modules.md` §2). This document grows
phase by phase alongside the code — it is not a complete security model yet.
Referenced by `docs/architecture.md` and ADR-0003.

**Phase 0** shipped the egress guard only. **Phase 3** adds scan
authorization, ownership verification and the audit-trail writer (§3-§5
below) — the rate governor and abuse heuristics remain future work (§6).
Redaction (`redact()`) is implemented in `packages/core`, not here, since it
has no I/O and no security *decision* to make — see `docs/modules.md` §1.

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
| Rate governor (per-account, per-target-host, global, Redis-backed) | `packages/security` | Phase 6/7 — Phase 3 uses a minimal DB-derived ceiling instead, see §3 |
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
   the full Redis-backed governor is Phase 6/7) → **deny**, code
   `RATE_LIMIT_EXCEEDED`.
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

## References

ADR-0001, ADR-0003 (including its Phase 3 addendum), `docs/architecture.md`
§7 and §15 (numbered as such in
`docs/prooflight-vision-and-architecture.md`), `docs/modules.md` §2, §2a, §2b,
`docs/data-model.md`.
