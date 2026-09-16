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

**Quota enforcement (Phase 7, returning submitters only).** A brand-new
submitter (no existing account for this email) takes the unchanged,
no-lookup path above — zero prior usage of anything to exceed. For a
*returning* submitter, two `vigilo_billing` checks run after
`resolve_authorization()` allows the request and before anything is
created: the target's origin, if new, is checked against the account's
plan's `TARGETS` limit (closing a real gap — this used to auto-create a
`Target` with no quota check at all, independent of `POST /v1/targets`'
own check below); then the account's rolling-30-day scan count is checked
against the plan's `SCANS_MONTHLY` limit. Either denial is audited
(`action="quota_exceeded"`) and committed before the error response, same
discipline as the `scan_denied` branch. Separately, `requested_tier:
"active"` for a returning account now also requires
`entitlements(account.plan_id).active_tier_allowed` — Free does not
include active tier, so a fully verified ownership proof alone downgrades
to `passive` on Free, same "downgrade, not a rejection" ADR-0003 pattern
as an unverified proof.

**Errors**: `422` malformed URL/email, `403` denied (denylisted, opted out,
or rate-limited — see `body.detail`/`context` for `resolve_authorization()`'s
reason), `429` `QUOTA_EXCEEDED` (returning submitters only, see above).

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
`scoring` or later. Full per-finding detail is **not** exposed here — see
`GET /v1/scans/{id}/report` below.

**Errors**: `404` unknown job id.

## `GET /v1/me` — first call after a Clerk sign-in

Auth required. Auto-provisions the `Account` on first call (see
`docs/data-model.md`'s anonymous/authenticated merge behavior) plus its
default `Project`.

**Response `200`**

```json
{
  "account_id": "...", "email": "owner@example.com", "status": "active", "created_at": "...",
  "entitlements": {
    "plan_id": "free", "targets_limit": 1, "scans_per_month_limit": 3,
    "active_tier_allowed": false, "share_links_allowed": false,
    "monitoring_frequency": null, "api_keys_limit": null, "repo_connectors_limit": null
  }
}
```

`entitlements` (Phase 7) is `vigilo_billing.entitlements(account.plan_id)`,
computed fresh on every call — nothing here is cached or stored
separately from `accounts.plan_id`. `monitoring_frequency`/
`api_keys_limit`/`repo_connectors_limit` are Phase 8/9-shaped fields with
no enforcement behind them yet (no monitor, API key, or repo connector
exists to restrict).

**Errors**: `401` missing/invalid/expired token, or a token whose claims
have no email and no prior linked account.

## `POST /v1/targets` — register a target under the caller's account

Auth required.

**Request**: `{ "origin": "https://example.com" }` → **Response `201`**: a
`TargetResponse` (see below).

**Quota enforcement (Phase 7).** If `origin` isn't already a tracked
target for the caller's project, the account's plan `TARGETS` limit is
checked first (re-adding an already-known origin is idempotent and never
counts against quota). `POST /v1/scans` enforces the identical check for
the origin it auto-creates a target for — see that endpoint's note above.

**Errors**: `422` malformed origin, `429` `QUOTA_EXCEEDED`.

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

## `GET /v1/scans/{scan_job_id}/report` — the full per-finding report (Phase 4)

Optional auth: a bearer token is not required — the report renders for
anyone holding the unguessable `scan_job_id`, same posture as `GET
/v1/scans/{id}` — but when present it's used to compute `is_owner`, so the
frontend can show owner-only controls (PDF export, share-link management)
without a second round trip.

**Response `200`**

```json
{
  "scan_job_id": "...",
  "is_owner": true,
  "target_origin": "https://example.com",
  "registry_version": "0.1",
  "score": 92.0,
  "grade": "A",
  "counts_by_severity": { "high": 1 },
  "generated_at": "2026-09-13T19:00:00Z",
  "findings": [
    {
      "check_id": "VG-HDR-001",
      "category": "headers",
      "title": "...",
      "severity": "high",
      "confidence": "confirmed",
      "verdict": "failed",
      "summary": "...",
      "remediation": "...",
      "references": ["https://..."],
      "evidence": {
        "matched_indicator": "...",
        "request_summary": "...",
        "redaction_applied": null,
        "captured_at": "..."
      },
      "fingerprint": "..."
    }
  ]
}
```

**Errors**: `404` unknown job, `409` the job exists but hasn't reached
scoring yet — distinguishes "keep polling" from "wrong id."

## `POST /v1/scans/{scan_job_id}/report/pdf` — request a PDF render

No auth required. Idempotent: finds-or-creates the `format="pdf"` `Report`
row and enqueues `render_report_pdf_job` only if one isn't already
pending or complete.

**Response `202`**: `{ "report_id": "...", "status": "pending", "download_url": null }`

## `GET /v1/scans/{scan_job_id}/report/pdf` — poll PDF render status

No auth required. Same response shape as above; `download_url` is
`/v1/reports/{report_id}/download` once `status` is `"complete"`.

## `GET /v1/reports/{report_id}/download` — stream the rendered PDF

No auth required. `Content-Type: application/pdf`.

**Errors**: `404` for an unknown report id or one that hasn't finished
rendering — the same code covers both, deliberately, since `get_report_pdf_bytes()`
doesn't distinguish "doesn't exist" from "not ready" at this endpoint.

## `POST /v1/scans/{scan_job_id}/share-links` — create a share link

Auth required, caller must own the target. Requires
`entitlements(account.plan_id).share_links_allowed` (Phase 7) — Free does
not include share links; checked before the `format="html"` `Report` row
is found-or-created (its content is never actually stored — see
`docs/data-model.md`).

**Request**: `{ "expires_in_days": 30 }` (optional; omit or `null` for no expiry)

**Response `201`**

```json
{ "share_link_id": "...", "token": "...", "url": "https://.../share/...", "expires_at": "2026-10-13T19:00:00Z" }
```

`token` is returned once, at creation time — only its SHA-256 hash is
persisted (`share_links.token_hash`).

**Errors**: `404` scan not owned/found, `409` report not ready, `429`
`QUOTA_EXCEEDED` (plan doesn't include share links).

## `GET /v1/scans/{scan_job_id}/share-links` — list share links

Auth required, caller must own the target. Never returns `token_hash`.

**Response `200`**: `[{ "share_link_id": "...", "expires_at": null, "revoked_at": null, "view_count": 3, "created_at": "..." }]`

## `POST /v1/share-links/{share_link_id}/revoke` — revoke a share link

Auth required, caller must own the target — ownership is traced
`share_link → report → scan → target`. `404`, not `403`, on ownership
mismatch, matching `targets.py`'s existing precedent.

**Response `200`**: `{ "share_link_id": "...", "revoked_at": "2026-09-15T12:00:00Z" }`

## `GET /v1/share/{token}` — resolve a share link

No auth. Public by design. Increments `view_count` on every successful
resolution.

**Response `200`**: the same shape as `GET /v1/scans/{id}/report`, with
`scan_job_id`/`is_owner` both `null`.

**Errors**: `404` unknown token; `410` expired or revoked (two distinct
`ErrorCode`s, same HTTP status — the difference is only in `body.code`).

---

## `POST /v1/billing/checkout` — start a Paddle checkout (Phase 7)

Auth required.

**Request**: `{ "plan_id": "builder" }` → **Response `200`**:
`{ "checkout_url": "https://checkout.paddle.com/checkout?..." }` — a
templated hosted-checkout URL (`vigilo_integrations.billing.create_checkout_url()`),
not a server-to-server API call. Completing checkout happens entirely on
Paddle's hosted page; this account's plan only actually changes once the
resulting `subscription.created` webhook arrives below.

**Errors**: `500` `BILLING_PROVIDER_ERROR` if Paddle isn't configured
(`PADDLE_VENDOR_ID`/`PADDLE_PRICE_ID_*` unset) or `plan_id` has no
configured price (e.g. `"free"`).

## `POST /v1/billing/webhook` — Paddle subscription events (Phase 7)

**No auth** — deliberately public. Paddle authenticates itself via the
`Paddle-Signature` header (HMAC-SHA256 over the raw request body), verified
before the body is parsed as JSON at all. See `docs/security.md` §7 for the
full attack-surface writeup, including the disclosed replay-protection gap.

**Behavior.** `verify_webhook_signature()` (`401` on failure) →
`parse_webhook_event()` → `interpret_webhook_event()`, which recognizes
`subscription.created`/`updated`/`canceled` and raises
`UnrecognizedWebhookEvent` for anything else or a malformed payload of a
recognized type — either case returns `200`/no-op rather than an error, to
avoid triggering Paddle's retry logic for events this integration doesn't
act on. A recognized event looks up the account by
`event.account_email` (`200`/no-op if unknown) and applies it via
`vigilo_identity.upsert_subscription()`, which cascades `accounts.plan_id`
(to the new plan if `status == "active"`, to `"free"` on `canceled`) and
writes an `audit_events` row (`action="subscription_updated"`).

**Response `200`**: `{ "status": "applied" }` or `{ "status": "ignored" }`.

**Errors**: `401` invalid/missing signature.

---

## Error-code → HTTP status mapping (`vigilo_api/errors.py`)

| `ErrorCode` | Status |
| --- | --- |
| `NOT_FOUND`, `SCAN_JOB_NOT_FOUND`, `OWNERSHIP_PROOF_NOT_FOUND`, `REPORT_NOT_FOUND`, `SHARE_LINK_NOT_FOUND` | 404 |
| `VALIDATION_ERROR`, `TARGET_INVALID` | 422 |
| `TARGET_UNVERIFIED`, `TARGET_OPTED_OUT`, `TIER_NOT_PERMITTED` | 403 |
| `RATE_LIMIT_EXCEEDED`, `QUOTA_EXCEEDED` | 429 |
| `OWNERSHIP_PROOF_EXPIRED`, `SHARE_LINK_EXPIRED`, `SHARE_LINK_REVOKED` | 410 |
| `INVALID_STATE_TRANSITION`, `REPORT_NOT_READY` | 409 |
| `PDF_RENDER_FAILED`, `BILLING_PROVIDER_ERROR`, and anything else | 500 |

---

## Not yet built (later phases)

Multi-project management endpoints (every account gets exactly one default
project today — see `docs/data-model.md`), outbound webhooks and API keys
for third-party integrations (Phase 9), the public REST API's
rate-limited, key-authenticated surface distinct from this
session-authenticated one (Phase 9), the MCP server (Phase 9). Billing
endpoints shipped in Phase 7 (above) — stubbed against Paddle, no real
account.
