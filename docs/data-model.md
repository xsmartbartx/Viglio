# Data model

## Purpose

The authoritative, column-level spec for Vigilo's persisted schema, owned by
`packages/persistence` (the shared SQLAlchemy `Base`/engine/session) plus
each table's owning module (`packages/identity`, `packages/project`,
`packages/orchestrator`, `packages/security`). Source of truth for the
schema itself is the Alembic migrations under
`packages/persistence/migrations/versions/`; this document explains what
those migrations mean and why, and calls out every place Phase 3's actual
implementation deviates from the entity table in
`docs/prooflight-vision-and-architecture.md` §6.1.

Phase 3 implemented 8 of that table's ~17 entities — exactly the ones its
exit criteria needed. Phase 4 added two more, `Report` and `ShareLink`.
Phase 5 adds `remediation_cache` — a deliberate addition beyond the domain
model's own entity table, same pattern as `scans.bundle_id`: the domain
model doesn't name a remediation cache, but
`docs/adr/ADR-0004-llm-boundary.md` and the Prooflight doc's own risk
register ("caching by fingerprint") require one. `MonitorSchedule`, `Alert`,
`ApiKey`, `Subscription`, `ScoreSnapshot` and a standalone `Evidence` table
remain deferred to the phases that actually need them (Phase 7 billing,
Phase 8 monitoring).

---

## accounts (`packages/identity`)

| Column | Type | Notes |
| --- | --- | --- |
| `id` | UUID, PK | |
| `email` | varchar(320), unique, indexed | |
| `status` | varchar(32) | `anonymous` \| `active` \| `suspended` |
| `plan_id` | varchar(64), nullable | Placeholder — billing is Phase 7 |
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
| `branding_profile_id` | varchar(64), nullable | Placeholder — no such entity exists yet, same pattern as `accounts.plan_id` |
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
in code is the source of truth; no DB mirror exists), `ScoreSnapshot`
(Phase 8's score-history charts), `MonitorSchedule`/`Alert` (Phase 8),
`ApiKey` (Phase 9's public API), `Subscription` (Phase 7).
