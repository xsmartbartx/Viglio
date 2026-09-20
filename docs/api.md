# API

## Purpose

The HTTP surface `packages/modules.md` §12 documents at a contract level;
this is the concrete Phase 3 endpoint list. No domain logic lives in a
handler — each one validates, delegates to a module's repository/service
functions, and serialises the result, per that module's own boundary rule.

Base URL: whatever `apps/api` is deployed at. Every endpoint is under `/v1`
except `GET /badge/{target_id}.svg` (Phase 8) — deliberately unversioned
and prefix-free, since it's meant to be embedded by URL in a third-party
`<img>` tag, not called as part of the versioned API contract — and except
`/public/v1/*` (Phase 9), a separate key-authenticated surface, see below.
Auth: a Clerk session JWT as `Authorization: Bearer <token>`,
verified against `CLERK_JWKS_URL` (`packages/apps/api/src/vigilo_api/auth.py`),
for every `/v1/*` route; `/public/v1/*` is authenticated by API key
instead (its own section below). Errors: any `StructuredError` raised
inside a handler is mapped to an HTTP status by
`vigilo_api.errors.handle_structured_error`; the body is always
`{"code": "...", "message": "...", "context": {...}}` — except
`/public/v1/*`'s auth/scope/rate-limit failures, which are plain
`HTTPException`s (see that section).

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
    "monitoring_frequency": null, "monitors_limit": 0,
    "api_keys_limit": 0, "api_rate_limit_per_minute": null,
    "white_label_allowed": false, "repo_connectors_limit": null
  }
}
```

`entitlements` is `vigilo_billing.entitlements(account.plan_id)`, computed
fresh on every call — nothing here is cached or stored separately from
`accounts.plan_id`. `monitoring_frequency`/`monitors_limit` are enforced as
of Phase 8 (`POST /v1/targets/{id}/monitors` below); `api_keys_limit`/
`api_rate_limit_per_minute`/`white_label_allowed` are enforced as of Phase 9
(`POST /v1/me/api-keys`, `/public/v1/*`, `PUT /v1/me/branding-profile`
below). `repo_connectors_limit` remains a Phase-9-shaped field with no
enforcement behind it — the repo connector itself is explicitly deferred
past Phase 9, see `docs/build-roadmap.md`.

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

## `GET /v1/targets` — list the caller's targets

Auth required. Added for the self-serve dashboard (`apps/web`'s
`/dashboard/targets`) — every other target endpoint already required
knowing a `target_id` in advance. No quota check; listing never consumes
quota, same as `GET /v1/targets/{id}` below.

**Response `200`**: `[TargetResponse, ...]`, oldest-first, scoped to the
caller's own (default) project only.

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
  "target_id": "...",
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

`target_id` (Phase 8) lets `apps/web` link into the monitoring dashboard
(`/targets/{id}/monitoring`) without a second lookup — like `scan_job_id`
and `is_owner`, it's `null` on `GET /v1/share/{token}`'s response below
(the shared, public view never exposes the owner's internal ids).

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

## `GET /v1/plans` — plan comparison data

No auth — genuinely public, no `AccountDep`/`SessionDep`, reads the static
in-memory `PLANS` dict directly. Added for the self-serve dashboard's
billing/upgrade page (`apps/web`'s `/dashboard/billing`).

**Response `200`**: `[PlanResponse, ...]`, one entry per `vigilo_billing.PlanId`
(`free`/`builder`/`studio`/`business`), field-for-field identical to
`EntitlementsResponse` above. **Deliberately no price field** — no dollar
amount exists anywhere in this codebase (not in `brand.config.json`, not
in `vigilo_billing.models.Plan`, not in any schema); the actual price
lives only inside Paddle's own hosted checkout page, reached via
`POST /v1/billing/checkout` below. The dashboard renders this as a
feature/limit comparison table and links out to checkout for the price.

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

## `POST /v1/targets/{target_id}/monitors` — enable monitoring (Phase 8)

Auth required, caller must own the target.

**Request**: `{ "cadence_hours": 168, "quiet_start_utc": null, "quiet_end_utc": null }`
(`quiet_start_utc`/`quiet_end_utc` optional, hour 0-23 UTC, both `null` = no
quiet hours).

**Behavior.** `cadence_hours` is validated against
`entitlements(account.plan_id).monitoring_frequency`: `null` → denied
outright (monitoring not on this plan); `"weekly"` → must equal exactly
`168`; `"daily+custom"` → any value `1`-`168`. If no monitor exists yet for
this target, the account's `MONITORS` quota is checked before creating one
— re-enabling or reconfiguring an existing monitor (this endpoint is
idempotent by target) never counts against it, matching
`POST /v1/targets`' own only-count-if-new precedent.

**Response `201`**

```json
{
  "monitor_id": "...", "target_id": "...", "cadence_hours": 168, "enabled": true,
  "next_run_at": "2026-09-23T19:00:00Z", "quiet_start_utc": null, "quiet_end_utc": null
}
```

**Errors**: `404` target not owned/found, `422` `cadence_hours` incompatible
with the plan, `429` `QUOTA_EXCEEDED` (monitoring not included in the plan,
or the `MONITORS` limit reached).

## `GET /v1/targets/{target_id}/monitors` — current monitor state

Auth required, caller must own the target.

**Response `200`**: same shape as the `POST` response above.

**Errors**: `404` target not owned/found, or no monitor exists for it yet.

## `POST /v1/monitors/{monitor_id}/disable` — turn off monitoring

Auth required, ownership checked via `Monitor.account_id` (denormalized —
`docs/data-model.md`) before anything is mutated. `404`, not `403`, on
ownership mismatch, matching `share_links.py`'s revoke precedent.

**Response `200`**: same shape as `POST .../monitors` above, with
`"enabled": false`.

**Errors**: `404` unknown monitor or not owned.

## `GET /v1/targets/{target_id}/scores` — score history

Auth required, caller must own the target. Most-recent-first.

**Response `200`**: `[{ "scan_id": "...", "score": 92.0, "grade": "A", "registry_version": "0.1", "created_at": "..." }]`

## `GET /v1/targets/{target_id}/alerts` — recent alerts

Auth required, caller must own the target. Most-recent-first, capped at 20.

**Response `200`**: `[{ "alert_id": "...", "type": "regressed", "severity": "high", "fingerprint": "...", "sent_at": "...", "created_at": "..." }]`

`type` is one of `new_critical`/`new_high`/`regressed`/`cert_expiry`/
`score_drop`/`scan_failed` (`docs/modules.md` §9). `severity`/`fingerprint`
are `null` for `score_drop`/`scan_failed`. `sent_at` is `null` until the
alert email actually delivers.

## `GET /badge/{target_id}.svg` — embeddable score badge (Phase 8)

**No auth** — deliberately public, and outside the `/v1` prefix (see
"Purpose" above). Meant for a plain `<img>` tag on the target owner's own
site. Reuses `Target.id` directly rather than a separate `public_id` —
see `docs/security.md` §8 for why that's safe.

**Response `200`**: `image/svg+xml`, `Cache-Control: public, max-age=3600`.
Renders the target's most recent scan's grade/score/date — nothing else;
`render_badge()`'s signature makes leaking finding data structurally
impossible, not just filtered out.

**Errors**: `404` unknown target, or no scan yet for it.

---

## `POST /v1/me/api-keys` — create an API key (Phase 9)

Auth required (Clerk session — this is session-authenticated management of
the keys that unlock `/public/v1/*` below, not itself part of that
surface). Gated on `entitlements(account.plan_id).api_keys_limit` via
`Meter.API_KEYS` (Free is `0` — no API access on Free).

**Request**: `{ "name": "CI pipeline", "scopes": ["scan:run", "scan:read"] }`

**Response `201`**

```json
{
  "api_key_id": "...", "name": "CI pipeline", "prefix": "vglo_aBc123De",
  "scopes": ["scan:run", "scan:read"], "api_key": "vglo_aBc123De..."
}
```

`api_key` (the plaintext) is returned once, at creation, and never
persisted or logged — only its SHA-256 hash is (`docs/data-model.md`'s
`api_keys.key_hash`), same posture as `share_links`' token.

**Errors**: `422` an unknown scope (see the scopes table below), `429`
`QUOTA_EXCEEDED`.

## `GET /v1/me/api-keys` — list API keys

Auth required. Never returns `key_hash` or the plaintext.

**Response `200`**: `[{ "api_key_id": "...", "name": "CI pipeline", "prefix": "vglo_aBc123De", "scopes": [...], "last_used_at": "...", "revoked_at": null, "created_at": "..." }]`

## `POST /v1/me/api-keys/{api_key_id}/revoke` — revoke a key

Auth required. `404`, not `403`, on ownership mismatch (checked by
re-listing the caller's own keys before mutating), matching
`share_links.py`'s revoke precedent.

**Response `200`**: same shape as the list entry above, with `revoked_at` set.

**Errors**: `404` unknown key or not owned.

## `PUT`/`GET /v1/me/branding-profile` — white-label configuration (Phase 9)

Auth required. Gated on `entitlements(account.plan_id).white_label_allowed`
— only the Business plan includes it, `QuotaExceeded` (`429`) otherwise.
`GET` returns all-`null` fields rather than `404` for an account with no
profile configured yet (found-or-created semantics, mirroring
`upsert_branding_profile()`'s own idempotence).

**Request** (`PUT`): `{ "logo_url": "https://...", "primary_color": "#0ea5e9", "footer_text": "...", "custom_domain": "reports.example.com" }`
— every field optional; omitted fields are left unchanged, not cleared.

**Response `200`**: `{ "logo_url": "...", "primary_color": "...", "footer_text": "...", "custom_domain": "..." }`

`custom_domain` is stored and returned as presentation metadata only — see
`docs/self-hosting.md`'s custom-domain note; Vigilo does not provision DNS
or TLS for it. A configured profile is automatically included as
`ScanReportResponse.branding` on both `GET /v1/scans/{id}/report` and
`GET /v1/share/{token}` for any target the account owns — `null` for every
other account, so `apps/web` never needs to check the plan itself.

**Errors**: `429` `QUOTA_EXCEEDED` (`PUT` only — plan doesn't include
white-labeling).

---

## Key-authenticated public API (`/public/v1/*`, Phase 9)

A REST + SSE surface distinct from everything above: authenticated by
`Authorization: Bearer vglo_...` (an API key from `POST /v1/me/api-keys`),
never a Clerk session. Every route requires a scope, checked against the
key's own `scopes`, and is rate-limited per **account** (one shared budget
across all of that account's keys) at
`entitlements(account.plan_id).api_rate_limit_per_minute` requests/minute
— `null` (Free) means no key can be issued at all, since `api_keys_limit`
is `0` on Free.

**Auth/scope/rate-limit errors are plain `HTTPException`s, not
`StructuredError`s** — the body is `{"detail": "..."}`, not this
document's usual `{"code", "message", "context"}` shape. This is a
deliberate, narrow deviation: `api_key_auth.py` sits in front of every
route as a FastAPI dependency, before any handler (and thus before
`vigilo_api.errors.handle_structured_error`'s usual error path) runs.

| Status | Cause |
| --- | --- |
| `401` | missing/malformed bearer token, or the key is unknown/revoked |
| `403` | the key's scopes don't include the one this route requires |
| `429` | rate limit exceeded — response includes a `Retry-After: <seconds>` header |

**Scopes**: `scan:run`, `scan:read`, `project:read`, `report:read`,
`monitor:read`, `monitor:write`.

**Ownership.** Every resource lookup below checks that the target/scan
belongs to the key's own account and returns `404` (never `403`) on a
mismatch — deliberately unlike `GET /v1/scans/{id}` above, which is public
by design (an unguessable UUID, no ownership check at all). A scoped API
key must never let one caller enumerate another account's resources by
guessing an id.

### `POST /public/v1/scans` (`scan:run`)

Same request/response shape as `POST /v1/scans` above, minus the `email`
field — the account is already known from the key. Reuses the identical
`resolve_authorization()`/quota machinery, including the `TARGETS`/
`SCANS_MONTHLY` checks for a target/scan-count the account has already
used elsewhere (session-authenticated and public-API usage share one
quota, not separate ones).

### `GET /public/v1/scans/{scan_job_id}` (`scan:read`)

Same response shape as `GET /v1/scans/{id}` above.

### `GET /public/v1/scans/{scan_job_id}/stream` (`scan:read`)

Server-sent events, `Content-Type: text/event-stream`. Emits `data: {"status": "..."}\n\n`
on every status change (not on a fixed interval — polls internally at 1s),
closing the stream once the job reaches a terminal status or 120 seconds
elapse, whichever first. A client that needs the final report after the
stream closes calls `GET .../report` below rather than relying on the
stream to deliver it inline.

### `GET /public/v1/scans/{scan_job_id}/report` (`report:read`)

Same response shape as `GET /v1/scans/{id}/report` above, always with
`is_owner: true` (there is no unauthenticated caller on this surface) and
`branding` populated per the white-label note above.

### `GET /public/v1/scans/{scan_job_id}/findings` (`report:read`)

`ReportFindingResponse[]` — just `report.findings` from the endpoint
above, as its own named resource (the vision doc's literal "list
findings").

### `GET /public/v1/scans/{scan_job_id}/report.sarif` (`report:read`)

The same findings as `.../report` above, rendered as a SARIF 2.1.0
document (`Content-Type: application/sarif+json`) for GitHub Code
Scanning and similar tooling. Only `FAILED`/`INCONCLUSIVE` findings become
SARIF `results` — `PASSED`/`NOT_APPLICABLE` are never emitted, matching
SARIF's own "report what needs attention" convention. Every check that has
an emitted result also gets a `rules[]` entry, tagged with its CWE id when
`docs/check-catalog.md`'s CWE column has one for it.

**A genuine adaptation, not a perfect fit**: GitHub's SARIF ingestion
expects `results[].locations[].physicalLocation.artifactLocation.uri` to
be a repo-relative source file with a line/column — Vigilo's findings are
about a live deployed URL, which has neither. This endpoint uses the
scanned origin as the location's `uri` (honest about there being no file)
with an inert region. See `packages/reporting/src/vigilo_reporting/sarif.py`'s
module docstring for the full reasoning, and `docs/github-action.md` for
the primary way most users will actually consume this format (the
zero-account `.github/actions/scan` GitHub Action, which produces the
same SARIF shape from the standalone CLI rather than this endpoint).

### `GET /public/v1/targets/{target_id}/scores` (`report:read`)

Same shape as `GET /v1/targets/{id}/scores` above.

### `GET /public/v1/projects` (`project:read`)

`[{ "project_id": "...", "name": "...", "created_at": "..." }]` — the
account's one default project (every account still gets exactly one, see
`docs/data-model.md`'s "Deferred entities").

### `POST`/`GET /public/v1/targets/{target_id}/monitors` (`monitor:write`/`monitor:read`), `POST /public/v1/monitors/{monitor_id}/disable` (`monitor:write`)

Same request/response shapes and quota rules as the session-authenticated
monitoring endpoints above.

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
project today — see `docs/data-model.md`). A repo connector and its
endpoints — explicitly deferred out of Phase 9 to its own future phase, see
`docs/build-roadmap.md`: it's a wholly new subsystem (GitHub auth, a new
evidence source, new scanning logic) comparable in size to Phase 7 or 8 by
itself, not a natural extension of anything Phase 9 built. Outbound
webhooks for third-party integrations remain unbuilt too (only the MCP
server and the key-authenticated REST API shipped as Phase 9's
distribution channels — see the public API section above and
`docs/modules.md` §13). Billing endpoints shipped in Phase 7 (above) —
stubbed against Paddle, no real account. Monitoring endpoints shipped in
Phase 8 (above); webhook delivery for alerts (the vision doc's "email in
v1, webhook in v2" framing, `docs/modules.md` §10) remains v2 — email is
the only channel implemented.
