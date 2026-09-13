# API

## Purpose

The HTTP surface `packages/modules.md` §12 documents at a contract level;
this is the concrete Phase 3 endpoint list. No domain logic lives in a
handler — each one validates, delegates to a module's repository/service
functions, and serialises the result, per that module's own boundary rule.

Base URL: whatever `apps/api` is deployed at, no version-independent prefix
beyond `/v1`. Auth: a Clerk session JWT as `Authorization: Bearer <token>`,
verified against `CLERK_JWKS_URL` (`packages/apps/api/src/vigilo_api/auth.py`).
Errors: any `StructuredError` raised inside a handler is mapped to an HTTP
status by `vigilo_api.errors.handle_structured_error`; the body is always
`{"code": "...", "message": "...", "context": {...}}`.

---

## `POST /v1/scans` — the anonymous free-scan path (exit criterion a)

No auth required.

**Request**

```json
{ "target_url": "https://example.com", "email": "owner@example.com", "requested_tier": "passive" }
```

`requested_tier` is optional, defaults to `"passive"`.

**Response `202`**

```json
{ "scan_job_id": "...", "status": "authorized", "granted_tier": "passive" }
```

**Behavior.** `validate_target_url()` → `resolve_authorization()` → the
decision is written to `audit_events` and **committed** → only then is
`run_scan_job` enqueued via ARQ. A denied request never creates an
`Account`/`Target`/`ScanJob` row — only the audit event. This ordering is
ADR-0003's binding requirement ("written to the audit trail before the scan
is queued, not after"), not a stylistic choice.

**Errors**: `422` malformed URL/email, `403` denied (denylisted, opted out,
or rate-limited — see `body.detail`/`context` for `resolve_authorization()`'s
reason).

## `GET /v1/scans/{scan_job_id}` — poll for a result

No auth required (the id is an unguessable UUID).

**Response `200`**

```json
{
  "scan_job_id": "...",
  "status": "complete",
  "target_origin": "https://example.com",
  "tier": "passive",
  "score": 92.0,
  "grade": "A",
  "counts_by_severity": { "high": 1 },
  "finished_at": "2026-09-13T19:00:00Z"
}
```

`score`/`grade`/`counts_by_severity` are `null` until the job reaches
`scoring` or later. Full per-finding detail is **not** exposed here — that's
Phase 4's report UI; a completed free scan's findings arrive via the
emailed report, not this endpoint.

**Errors**: `404` unknown job id.

## `GET /v1/me` — first call after a Clerk sign-in

Auth required. Auto-provisions the `Account` on first call (see
`docs/data-model.md`'s anonymous/authenticated merge behavior) plus its
default `Project`.

**Response `200`**

```json
{ "account_id": "...", "email": "owner@example.com", "status": "active", "created_at": "..." }
```

**Errors**: `401` missing/invalid/expired token, or a token whose claims
have no email and no prior linked account.

## `POST /v1/targets` — register a target under the caller's account

Auth required.

**Request**: `{ "origin": "https://example.com" }` → **Response `201`**: a
`TargetResponse` (see below).

## `GET /v1/targets/{target_id}` — exit criterion (b)'s poll target

Auth required, caller must own the target (its project's `account_id`
matches). Polled to observe `verification_status` flip from `passive` to
`active`.

**Response `200`**

```json
{
  "target_id": "...",
  "origin": "https://example.com",
  "verification_status": "active",
  "verified_at": "2026-09-13T19:05:00Z",
  "verification_method": "dns_txt"
}
```

**Errors**: `404` for a target that doesn't exist or belongs to someone else
(deliberately not `403`, so ownership can't be probed by status code).

## `POST /v1/targets/{target_id}/verification` — issue an ownership proof

Auth required, caller must own the target.

**Request**: `{ "method": "dns_txt" }` (one of `dns_txt` \| `wellknown_file`
\| `meta_tag` \| `email` — `email` is accepted by the schema but its worker
job always fails with "not implemented," per the Phase 3 scope trim).

**Response `201`**

```json
{
  "proof_id": "...",
  "method": "dns_txt",
  "nonce": "aBc123...",
  "instructions": "Add a DNS TXT record: vigilo-site-verification=aBc123..."
}
```

`instructions` is built from `brand.config.json`'s `dnsVerificationKey`/
`wellKnownPath` namespace values — never hardcoded.

## `POST /v1/targets/{target_id}/verification/{proof_id}/check` — "check now"

Auth required, caller must own the target.

**Response `202`**: `{ "proof_id": "...", "status": "checking" }`.

**Behavior.** Always enqueues `verify_ownership_job` — **never** runs a
verification method inline in this handler, for every method, not only the
ones that fetch the target. See the ADR-0003 Phase 3 addendum for why this
is uniform rather than a special case for the network-touching methods
only.

**Errors**: `404` unknown proof, or a proof that doesn't belong to
`target_id`.

---

## Error-code → HTTP status mapping (`vigilo_api/errors.py`)

| `ErrorCode` | Status |
| --- | --- |
| `NOT_FOUND`, `SCAN_JOB_NOT_FOUND`, `OWNERSHIP_PROOF_NOT_FOUND` | 404 |
| `VALIDATION_ERROR`, `TARGET_INVALID` | 422 |
| `TARGET_UNVERIFIED`, `TARGET_OPTED_OUT`, `TIER_NOT_PERMITTED` | 403 |
| `RATE_LIMIT_EXCEEDED`, `QUOTA_EXCEEDED` | 429 |
| `OWNERSHIP_PROOF_EXPIRED` | 410 |
| `INVALID_STATE_TRANSITION` | 409 |
| anything else | 500 |

---

## Not yet built (later phases)

Project management endpoints (multiple projects per account — Phase 4),
full per-finding report retrieval and PDF export (Phase 4), webhooks and
API keys (Phase 9), billing/entitlement endpoints (Phase 7), the public
REST API's rate-limited, key-authenticated surface distinct from this
session-authenticated one (Phase 9), the MCP server (Phase 9).
