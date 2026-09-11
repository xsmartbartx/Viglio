# Security

## Purpose

Detail for the `security` module (`docs/modules.md` §2). This document grows
phase by phase alongside the code — it is not a complete security model yet.
Referenced by `docs/architecture.md` and ADR-0003.

**Phase 0 scope:** the egress guard only. Authorization (`resolve_authorization`,
`verify_ownership`), the rate governor, and the audit-trail writer are
specified in ADR-0003 but not yet implemented — they need `Account`/`Target`
persistence that arrives in Phase 3. Redaction (`redact()`) is implemented in
`packages/core`, not here, since it has no I/O and no security *decision* to
make — see `docs/modules.md` §1.

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
| Scan authorization (`resolve_authorization`, `verify_ownership`) | `packages/security` | `Account`/`Target` persistence (Phase 3) |
| Rate governor (per-account, per-target-host, global) | `packages/security` | Redis-backed rate state (Phase 3) |
| Audit trail writer (append-only) | `packages/security` | Database schema (Phase 3) |
| Abuse heuristics (enumeration patterns, target churn) | `packages/security` | Scan history to detect patterns against (Phase 3+) |
| Redirect same-registrable-domain restriction | `packages/security/egress_guard.py` | Public-suffix-list dependency (Phase 1) |
| Worker network isolation (the scan zone has no route to internal services) | Deployment topology, not application code | Phase 1 deployment target |

## References

ADR-0001, ADR-0003, `docs/architecture.md` §7 and §15 (numbered as such in
`docs/prooflight-vision-and-architecture.md`), `docs/modules.md` §2.
