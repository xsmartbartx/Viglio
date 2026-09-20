# Data model

## Purpose

The authoritative, column-level spec for Vigilo's persisted schema, owned by
`packages/persistence` (the shared SQLAlchemy `Base`/engine/session) plus
each table's owning module (`packages/identity`, `packages/project`,
`packages/orchestrator`, `packages/security`, `packages/monitoring`).
Source of truth for the schema itself is the Alembic migrations under
`packages/persistence/migrations/versions/`; this document explains what
those migrations mean and why, and calls out every place the actual
implementation deviates from the entity table in
`docs/prooflight-vision-and-architecture.md` §6.1.

Phase 3 implemented 8 of that table's ~17 entities — exactly the ones its
exit criteria needed. Phase 4 added two more, `Report` and `ShareLink`.
Phase 5 adds `remediation_cache` — a deliberate addition beyond the domain
model's own entity table, same pattern as `scans.bundle_id`: the domain
model doesn't name a remediation cache, but
`docs/adr/ADR-0004-llm-boundary.md` and the Prooflight doc's own risk
register ("caching by fingerprint") require one. Phase 7 adds
`subscriptions`. Phase 8 adds `monitors`/`alerts` (named `MonitorSchedule`/
`Alert` in the domain model) but does *not* add a `ScoreSnapshot` table —
score history reads `scans` directly instead (see "Deferred entities"
below). Phase 9 adds `api_keys` and `branding_profiles` (the domain
model's `ApiKey`, plus a new entity the domain model doesn't name — see
that section below). A standalone `Evidence` table remains deferred.

---

## accounts (`packages/identity`)

| Column | Type | Notes |
| --- | --- | --- |
| `id` | UUID, PK | |
| `email` | varchar(320), unique, indexed | |
| `status` | varchar(32) | `anonymous` \| `active` \| `suspended` |
| `plan_id` | varchar(64), nullable | `null`/unrecognized resolves to `free` via `vigilo_billing.entitlements()` (Phase 7). Cascaded by `vigilo_identity.upsert_subscription()` — never written directly by request-handling code — whenever the `subscriptions` row below changes; see that table's notes. |
| `data_region` | varchar(32), nullable | Placeholder, unused until multi-region hosting exists |
| `clerk_user_id` | varchar(128), unique, nullable | **Deviation**: not in the Prooflight domain table. Maps a Clerk session's `sub` claim to this row. Nullable because a free scan creates an account from an email alone, before anyone has signed in. |
| `created_at` | timestamptz | |

**Deviation — the anonymous/authenticated merge.** The Prooflight domain
model doesn't address how an account created anonymously (free scan, exit
criterion a) reconciles with one created by signing in (exit criterion b).
Phase 3's answer:
`vigilo_identity.repository.get_or_create_account(session, email, clerk_user_id=None)`
looks up by `email` first; if a matching row exists and has no
`clerk_user_id` yet, it attaches the Clerk id and promotes `status` to
`active` in place, rather than creating a second row. One account, one
email, regardless of which path created it first.

## subscriptions (`packages/identity`, added Phase 7)

| Column | Type | Notes |
| --- | --- | --- |
| `id` | UUID, PK | |
| `account_id` | UUID, FK `accounts.id`, indexed | |
| `plan_id` | varchar(64) | `free` \| `builder` \| `studio` \| `business` (`vigilo_billing.PlanId`) |
| `status` | varchar(16) | `active` \| `canceled` |
| `provider` | varchar(32) | `paddle` today — provider-agnostic column, only one provider implemented |
| `provider_subscription_id` | varchar(128), unique | The provider's own subscription id. **Not** unique on `account_id` alone — a provider issues a new subscription id on plan change or renewal, so rows accumulate over time rather than being updated in place; `get_subscription_by_account()` returns the most recently created row. |
| `current_period_end` | timestamptz, nullable | From the provider's webhook payload; `null` if the provider didn't supply one (e.g. a canceled subscription) |
| `created_at` | timestamptz | |

**Deviation — lives in `identity`, not a `billing`-owned table.** The
Prooflight domain model doesn't specify an owning module for `Subscription`;
`packages/billing` itself is deliberately ORM-free (`docs/modules.md` §11's
deviation note), so this table lives next to `accounts` instead, owned by
`packages/identity`.

**Cascade.** `upsert_subscription()` is the only writer, keyed on
`provider_subscription_id` (a replayed webhook event updates the existing
row rather than duplicating it), and in the same flush sets
`accounts.plan_id` to `plan_id` when `status == "active"`, or to `"free"`
otherwise. This is why a canceled subscription doesn't strand an account on
its old paid plan forever: `vigilo_billing.entitlements()` only ever reads
`accounts.plan_id`, never queries this table directly, so the cascade is
what actually revokes the entitlement.

## api_keys (`packages/identity`, added Phase 9)

| Column | Type | Notes |
| --- | --- | --- |
| `id` | UUID, PK | |
| `account_id` | UUID, FK `accounts.id`, indexed | |
| `name` | varchar(128) | User-supplied label, e.g. "CI pipeline" |
| `prefix` | varchar(16) | First 12 chars of the plaintext key (`vglo_...`) — shown in the management UI so an owner can tell keys apart without re-displaying the secret |
| `key_hash` | varchar(64), unique, indexed | `sha256(plaintext).hexdigest()` — the plaintext is never stored, same posture as `share_links.token_hash` |
| `scopes` | JSON (`list[str]`) | Subset of `scan:run`, `scan:read`, `project:read`, `report:read`, `monitor:read`, `monitor:write` — see `docs/api.md` |
| `last_used_at` | timestamptz, nullable | Stamped by `require_api_key()` on every authenticated request |
| `revoked_at` | timestamptz, nullable | Set by `revoke_api_key()`; a revoked key still exists (audit trail) but `require_api_key()` rejects it |
| `created_at` | timestamptz | |

The plaintext key (`f"vglo_{secrets.token_urlsafe(32)}"`) is returned once,
at creation (`POST /v1/me/api-keys`), matching `share_links`'s
plaintext-once pattern exactly. `count_api_keys_for_account()` (live
`COUNT` of non-revoked rows) feeds `Meter.API_KEYS`, the same
live-`COUNT`-at-check-time pattern `monitors`/`Meter.MONITORS` already
established in Phase 8, rather than a separately maintained counter column.

## branding_profiles (`packages/identity`, added Phase 9)

| Column | Type | Notes |
| --- | --- | --- |
| `id` | UUID, PK | |
| `account_id` | UUID, FK `accounts.id`, unique, indexed | One profile per account — the plan's "client workspaces" scope resolved to its smallest faithful reading, not a new multi-tenant sub-account entity |
| `logo_url` | varchar(255), nullable | |
| `primary_color` | varchar(32), nullable | Rendered as the report's accent border color |
| `footer_text` | varchar(255), nullable | |
| `custom_domain` | varchar(255), nullable | Presentation metadata only — Vigilo does not provision DNS or TLS for it, see `docs/self-hosting.md`'s custom-domain note |
| `created_at` | timestamptz | |
| `updated_at` | timestamptz, `onupdate=func.now()` | |

Not in the Prooflight domain table at all — it names a "Business tier" for
white-labeling (§11) without specifying an entity for the configuration
itself. `upsert_branding_profile()` is the only writer, found-or-created
idempotently by `account_id`. Gated entirely by
`entitlements(account.plan_id).white_label_allowed` at the `apps/api`
layer, not by this table's own structure — a Free-tier account can have no
row at all, and `get_branding_for_target()` (`apps/api/src/vigilo_api/
report_rendering.py`) returns `None` for any account whose plan doesn't
allow white-labeling even if a stale row exists from a prior downgrade.

## projects (`packages/project`)

| Column | Type | Notes |
| --- | --- | --- |
| `id` | UUID, PK | |
| `account_id` | UUID, FK → `accounts.id`, indexed | |
| `name` | varchar(200) | Always `"Default"` in Phase 3 — no project-management UI yet (`get_or_create_default_project`), one project per account |
| `created_at` | timestamptz | |

## targets (`packages/project`)

| Column | Type | Notes |
| --- | --- | --- |
| `id` | UUID, PK | |
| `project_id` | UUID, FK → `projects.id`, indexed | |
| `origin` | varchar(255) | Canonical `scheme://host[:port]`, the output of `vigilo_core.validation.validate_target_url` |
| `verification_status` | varchar(16) | `passive` \| `active` (`vigilo_core.models.Tier`) |
| `verified_at` | timestamptz, nullable | |
| `verification_method` | varchar(32), nullable | `dns_txt` \| `wellknown_file` \| `meta_tag` \| `email` (`vigilo_core.models.VerificationMethod`) |
| `opt_out_flag` | boolean, default false | Manually set only in Phase 3 — automated `/.well-known/vigilo-optout.txt` fetching is a later-phase addition |
| `created_at` | timestamptz | |

Unique constraint on `(project_id, origin)`. Since Phase 3 gives every
account exactly one (default) project, this is equivalent in practice to
the domain model's "one target per origin per account," without literally
modeling account-level uniqueness.

## ownership_proofs (`packages/project`)

| Column | Type | Notes |
| --- | --- | --- |
| `id` | UUID, PK | |
| `target_id` | UUID, FK → `targets.id`, indexed | |
| `method` | varchar(32) | One of `VerificationMethod`'s values |
| `nonce` | varchar(64) | `secrets.token_urlsafe(32)` |
| `issued_at` | timestamptz | |
| `verified_at` | timestamptz, nullable | Set by `mark_proof_verified()` |
| `expires_at` | timestamptz, nullable | `verified_at + 90 days`, per ADR-0003 |

**Deviation — immutability is application-layer, not DB-layer.** The domain
model calls this row "immutable once verified." Phase 3 enforces that only
by convention (the repository never issues an `UPDATE` against an
already-verified proof) — a lighter guarantee than `audit_events`' DB-level
trigger below. Flagged here as a known, smaller guarantee, not silently
assumed equal.

## suppressions (`packages/project`, added post-Phase-9)

| Column | Type | Notes |
| --- | --- | --- |
| `id` | UUID, PK | |
| `target_id` | UUID, FK → `targets.id`, indexed | |
| `fingerprint` | varchar(128) | Same width/identity as `findings.fingerprint` — never a FK to `findings.id`, since every scan creates a fresh set of finding rows and a suppression must survive across scans |
| `check_id` | varchar(32) | Informational/display only — not part of uniqueness, since `fingerprint` already encodes it |
| `reason` | text | Free-text justification, required |
| `expires_at` | timestamptz, nullable | `null` = permanent. An expired suppression reverts to showing the finding again — it isn't deleted, just excluded by `get_suppressed_fingerprints_for_target()`'s `WHERE` clause |
| `created_by_account_id` | UUID, FK → `accounts.id` | Who accepted the risk |
| `created_at` | timestamptz | |

`UniqueConstraint(target_id, fingerprint)` — `create_suppression()` upserts
on this pair (re-suppressing an already-suppressed finding updates its
reason/expiry in place), matching `upsert_branding_profile()`'s exact
found-or-update precedent.

Closes the vision doc's `docs/prooflight-vision-and-architecture.md` §6.2
finding-lifecycle states (`acknowledged`/`muted`) as a target-scoped
suppression list rather than a full `Verdict`-enum retrofit. Applied at
three points, deliberately never at scoring — see `docs/security.md` §3
and `docs/modules.md` §2b/§9: report rendering (marked `suppressed: true`,
not removed), SARIF export (excluded from `results[]`/`rules[]`
entirely), and monitoring alerts (`detect_regression()` skips
`new_critical`/`new_high`/`regressed`/`cert_expiry` events and score-drop
hysteresis for a suppressed fingerprint). A scan's `score`/`grade` are
never recomputed from this table — they stay the one true, unfiltered
number.

## scan_jobs (`packages/orchestrator`)

| Column | Type | Notes |
| --- | --- | --- |
| `id` | UUID, PK | The public `scan_job_id` clients poll |
| `target_id` | UUID, FK → `targets.id`, indexed | |
| `tier` | varchar(16) | The *granted* tier, from `resolve_authorization()` |
| `requested_by` | varchar(255), nullable | **Deviation**: the domain model doesn't specify this field's shape. Phase 3 stores the requester's email address directly (not an account id) — it's what the report email is sent to, for both the anonymous and authenticated paths, without a second lookup. |
| `registry_version` | varchar(16) | e.g. `"0.1"` |
| `status` | varchar(16) | `queued` \| `authorized` \| `probing` \| `evaluating` \| `scoring` \| `reporting` \| `complete` \| `unreachable` \| `failed` \| `rejected` — the state machine in `docs/modules.md` §8 |
| `budget` | JSON, nullable | Column exists; request-budget enforcement is Phase 6 (roadmap scope trim) |
| `queued_at` | timestamptz | |
| `started_at` | timestamptz, nullable | Set on the `probing` transition |
| `finished_at` | timestamptz, nullable | Set on any terminal transition |

## scans (`packages/orchestrator`)

| Column | Type | Notes |
| --- | --- | --- |
| `id` | UUID, PK | |
| `job_id` | UUID, FK → `scan_jobs.id`, unique | One scan per job |
| `target_id` | UUID, FK → `targets.id`, indexed | |
| `registry_version` | varchar(16) | |
| `score` | float | |
| `grade` | varchar(4) | |
| `counts_by_severity` | JSON | `{severity: count}` |
| `duration_ms` | integer | |
| `tier` | varchar(16) | |
| `bundle_id` | varchar(64), nullable | **Deviation, deliberate addition**: the content-addressed id (`EvidenceBundle.compute_id()`) pointing at the sealed bundle in object storage. The domain model has no object-storage pointer on `Scan` — Phase 1/2 already made `EvidenceBundle` content-addressed and immutable, so this just wires that existing id through. `null` if the object-store write failed (non-fatal — see `packages/orchestrator/src/vigilo_orchestrator/jobs.py`). |
| `created_at` | timestamptz | |

No standalone `Evidence` table yet — the full bundle lives in object storage
(`vigilo_integrations.storage`, MinIO locally), referenced by `bundle_id`,
not modeled as per-finding relational rows.

## findings (`packages/orchestrator`)

| Column | Type | Notes |
| --- | --- | --- |
| `id` | UUID, PK | |
| `scan_id` | UUID, FK → `scans.id`, indexed | |
| `check_id` | varchar(32) | e.g. `VG-HDR-001` |
| `status` | varchar(16) | The check's `Verdict` (`passed`/`failed`/`inconclusive`/`not_applicable`) |
| `severity` | varchar(16) | |
| `confidence` | varchar(16) | |
| `title` | varchar(255) | |
| `summary` | text | |
| `evidence_id` | varchar(64), nullable | Free-text pointer into the bundle, not a separate `Evidence` table |
| `matched_indicator` | text, nullable | **Added Phase 4.** The concrete evidence string behind a finding (`Finding.evidence.matched_indicator`) — was computed at check-evaluation time and silently discarded before persistence until this phase, which made evidence panels unbuildable. Already redaction-safe by construction: every secret-detecting check routes through `vigilo_core.redact.redact()` before it ever becomes a `CheckResult.matched_indicator`. |
| `request_summary` | varchar(255), nullable | **Added Phase 4.** A short human-readable description of the request that produced the evidence (e.g. `"GET /"`). |
| `redaction_applied` | boolean, nullable | **Added Phase 4.** Persisted from `Finding.evidence.redaction_applied`. **Known gap, not fixed this phase:** `to_findings()` (`packages/checks/src/vigilo_checks/findings.py`) currently hardcodes this to `False` unconditionally, so the column is persisted honestly but the value itself doesn't yet reflect reality. The web UI deliberately does **not** surface a "redacted" badge from this column, since that signal would currently be misleading. |
| `fingerprint` | varchar(128) | Stable cross-scan identity, for the regression detection Phase 8 adds |

No `captured_at` column on `findings` — Phase 4's `EvidencePanel` reuses
`Scan.created_at` instead (`get_findings_for_scan()`'s reconstruction). Every
finding in a scan shares one evidence-bundle capture moment; the gap between
capture and persistence is milliseconds, so a per-finding timestamp would add
a column without adding real precision.

## reports (`packages/orchestrator`, added Phase 4)

| Column | Type | Notes |
| --- | --- | --- |
| `id` | UUID, PK | |
| `scan_id` | UUID, FK → `scans.id`, indexed | |
| `format` | varchar(16) | `"html"` \| `"pdf"` |
| `status` | varchar(16), default `"pending"` | `"pending"` \| `"complete"` \| `"failed"` — represents the PDF-render job's lifecycle. An `"html"` report is always created with `status="complete"` immediately: nothing is rendered ahead of time, the web page renders on request. |
| `artefact_uri` | varchar(255), nullable | Object-store key for a completed PDF (`reports/{report_id}.pdf`). Always `NULL` for `format="html"` — the HTML report has no stored artefact, `apps/web`'s report page renders it live from `GET /v1/scans/{id}/report` on every request. |
| `branding_profile_id` | varchar(64), nullable | **Still unused as of Phase 9** — `branding_profiles` now exists (see that section above), but `ScanReportResponse.branding` is resolved live per request by `get_branding_for_target()` (target → project → account → profile), not by a stored FK on the report row itself. This column remains a placeholder for a future "freeze the branding a PDF was rendered with" use case, distinct from the HTML report's always-live lookup. |
| `generated_at` | timestamptz, nullable | Set on completion |
| `created_at` | timestamptz | |

`UniqueConstraint(scan_id, format)` — at most one HTML report row and one PDF
report row per scan, found-or-created idempotently by
`get_or_create_html_report()`/`get_or_create_pdf_report()`.

## share_links (`packages/orchestrator`, added Phase 4)

| Column | Type | Notes |
| --- | --- | --- |
| `id` | UUID, PK | |
| `report_id` | UUID, FK → `reports.id`, indexed | |
| `token_hash` | varchar(64), unique | `sha256(token).hexdigest()` — plain SHA-256, not a slow KDF, is correct here: the token already carries ~256 bits of entropy (`secrets.token_urlsafe(32)`, matching `ownership_proofs.nonce`'s existing convention), it's a bearer capability token, not a low-entropy password. |
| `expires_at` | timestamptz, nullable | |
| `revoked_at` | timestamptz, nullable | |
| `view_count` | integer, default 0 | Incremented by `record_share_link_view()` on every successful `GET /v1/share/{token}` resolution |
| `created_at` | timestamptz | |

The plaintext token is returned once, at creation
(`POST /v1/scans/{id}/share-links`), and never persisted or logged.

## remediation_cache (`packages/orchestrator`, added Phase 5)

| Column | Type | Notes |
| --- | --- | --- |
| `id` | UUID, PK | |
| `fingerprint` | varchar(128) | `Finding.fingerprint` — `sha256(check_id + "\|" + target_origin)[:16]` (`packages/checks/src/vigilo_checks/findings.py`), stable across repeat scans of the same target for the same check. Column width matches `findings.fingerprint`'s, headroom beyond today's 16 hex chars. |
| `check_id` | varchar(32), indexed | Queryable, but not part of the uniqueness key — `fingerprint` already encodes it. |
| `registry_version` | varchar(16) | Part of the composite key (below) — a registry bump can write a fresh cache entry without clobbering an older scan's still-valid row for the prior version's `remediation_template`. |
| `explanation` | text | |
| `impact` | text | |
| `remediation_steps` | JSON (`list[str]`) | |
| `agent_prompt` | text | The paste-ready fix prompt — `docs/vision.md`'s and the README's headline promise. |
| `estimated_effort` | varchar(16), nullable | One of `trivial`/`small`/`medium`/`large` — a closed vocabulary, not free text, so the LLM's JSON response either validates cleanly or is discarded whole per `docs/adr/ADR-0004-llm-boundary.md`. |
| `generated_at` | timestamptz | |

`UniqueConstraint(fingerprint, registry_version)` — composite, not
`fingerprint` alone. Only rows with `source == "llm"` (a `RemediationPrompt`
field, not persisted here — every row in this table is, by construction, an
LLM result) are ever written; `packages/orchestrator/src/vigilo_orchestrator
/remediation.py`'s `cache_remediation()` no-ops for a template-sourced
result, since template text is free to recompute and shouldn't freeze a
finding at template quality once the provider becomes available.
`generate_remediations_job` (a new ARQ job, auto-enqueued right after scan
scoring — never inline in `run_scan_job`) is the only writer; report
rendering (`GET /v1/scans/{id}/report`, `GET /v1/share/{token}`) only ever
reads, never triggers generation itself.

## monitors (`packages/monitoring`, added Phase 8)

| Column | Type | Notes |
| --- | --- | --- |
| `id` | UUID, PK | |
| `target_id` | UUID, FK `targets.id`, unique, indexed | One monitor per target — `create_monitor()` is idempotent-by-target, matching `create_target()`'s idempotent-by-origin precedent. |
| `account_id` | UUID, FK `accounts.id`, indexed | **Deviation, deliberate**: denormalized. `Target` has no direct `account_id` (only via `project_id -> projects.account_id`); this avoids a two-hop join on every `due_monitors()`/entitlement-count query, matching `scans.target_id` existing alongside `scan_jobs.target_id`. |
| `cadence_hours` | integer | 168 for a `weekly`-only plan (Builder); 1-168 for a `daily+custom` plan (Studio). Validated against `vigilo_billing.entitlements().monitoring_frequency` at creation time, not stored as a separate string. |
| `enabled` | boolean | Set `false` by `disable_monitor()` — either the owner turning monitoring off, or `check_due_monitors_job` doing so automatically when a scheduled run's `resolve_authorization()` call denies outright (opted out/denylisted since creation). |
| `next_run_at` | timestamptz, indexed | `due_monitors(now)` filters on this. Recomputed by `compute_next_run_at()` every cycle — cadence plus jitter (±15 min, to avoid a recognizable scan signature) plus a quiet-hours push-forward. |
| `quiet_start_utc` | integer, nullable | Hour 0-23. Both null = no quiet hours. |
| `quiet_end_utc` | integer, nullable | |
| `pending_score_drop` | boolean | Hysteresis state for `score_drop` alerts (vision §10.3: "requires the drop to persist across two consecutive scans unless a critical is involved") — one bit of persisted state instead of a 3-scan lookback on every diff. |
| `created_at` | timestamptz | |

## alerts (`packages/monitoring`, added Phase 8)

| Column | Type | Notes |
| --- | --- | --- |
| `id` | UUID, PK | |
| `monitor_id` | UUID, FK `monitors.id`, indexed | |
| `target_id` | UUID, FK `targets.id`, indexed | Denormalized alongside `monitor_id`, same "redundant FK for a different query shape" precedent as `monitors.account_id` above — alert history stays queryable even if the owning monitor is later deleted. |
| `scan_id` | UUID, FK `scans.id`, indexed, **nullable** | Null for `scan_failed` — that alert fires when the job never reached `record_scan_result()`, so there is no `Scan` row to reference. Every other alert type always has one. |
| `type` | varchar(32) | `new_critical` \| `new_high` \| `regressed` \| `cert_expiry` \| `score_drop` \| `scan_failed`. No `resolved` — no alert type exists for it; see `docs/modules.md` §9. |
| `severity` | varchar(16), nullable | Null for `score_drop`/`scan_failed` (not per-finding). |
| `fingerprint` | varchar(128), nullable | Null for `score_drop`/`scan_failed`. |
| `dedupe_key` | varchar(200) | `f"{target_id}:{fingerprint or type}:{type}"` — kept for auditability, matching the vision's `(target_id, fingerprint, event_type)` framing. **Not** queried to suppress re-sends; dedup is structural — `detect_regression()` only ever emits an event on a state *transition*, so a fingerprint that stays failed across many scans produces no repeat event to begin with. |
| `sent_at` | timestamptz, nullable | Null until `notify()` actually delivers; set after the fact so a delivery failure doesn't hide that the alert was recorded. |
| `channel` | varchar(16) | `"email"` — the only channel this phase implements. |
| `created_at` | timestamptz | |

## audit_events (`packages/security`)

| Column | Type | Notes |
| --- | --- | --- |
| `id` | UUID, PK | |
| `account_id` | UUID, FK → `accounts.id`, nullable, indexed | Nullable — a denied scan against a denylisted domain may have no account yet |
| `actor` | varchar(64) | `"api"` or `"scanner"` — which process wrote the event |
| `action` | varchar(64) | `scan_authorized` \| `scan_denied` \| `scan_execution_denied` \| `ownership_verified` |
| `subject` | varchar(255) | Usually the target origin |
| `metadata` | JSON | Free-form, non-secret context (never a raw secret — everything here already passed through `vigilo_core.redact.redact()` if it was ever secret-shaped) |
| `occurred_at` | timestamptz | |

**Append-only, enforced at the database level** — not just application
discipline. `packages/persistence/migrations/versions/0002_audit_events_append_only.py`
adds a `BEFORE UPDATE OR DELETE OR TRUNCATE` trigger on this table that
unconditionally raises. This is a Postgres trigger, not a `REVOKE` grant:
the local/CI database has one owning role, and Postgres table owners bypass
`REVOKE`; a trigger enforces the guarantee regardless of which role runs
the statement. Proven by `packages/security/tests/test_audit_append_only.py`,
which runs the actual migrations and asserts `UPDATE`, `DELETE` and
`TRUNCATE` all raise.

---

## Cross-module foreign keys

Every FK above crosses a module boundary (e.g. `targets.project_id` →
`projects.id`, owned by the same module; `projects.account_id` →
`accounts.id`, owned by `identity`; `audit_events.account_id` →
`accounts.id`, owned by `identity`). All of them are declared by table name
string (`ForeignKey("accounts.id")`), never by importing another module's
`orm.py` class — there is one shared Postgres database, but no
module-to-module Python import for persistence models. This is what keeps
`packages/security`'s and `packages/orchestrator`'s dependency graphs
matching `docs/modules.md`'s documented edges despite every table living in
one physical schema.

## Deferred entities

Not yet modeled (see the phase that adds them): multi-`Project` UI/API
(every account still gets exactly one default project, no phase commits to
this yet), `Evidence` as its own relational table (no phase commits to this
yet — object storage has sufficed so far), `CheckDefinition` (the registry
in code is the source of truth; no DB mirror exists), a repo-connector
entity (explicitly deferred out of Phase 9 to its own future phase —
`docs/build-roadmap.md`'s Phase 9 entry has the full reasoning). `Subscription`
(Phase 7), `MonitorSchedule`/`Alert` (Phase 8, named `monitors`/`alerts`)
and `ApiKey` (Phase 9, named `api_keys` — see those sections above) are no
longer deferred. `ScoreSnapshot` never got built as its own table either —
Phase 8's score-history chart reads `scans` directly
(`list_scans_for_target()`, `docs/modules.md` §8), which already carries
`score`/`grade`/`created_at` per target; a dedicated snapshot table would
have duplicated it for no benefit.
