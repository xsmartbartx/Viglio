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

Phase 3 implements 8 of that table's ~17 entities — exactly the ones the
roadmap's exit criteria need. `Project`, `MonitorSchedule`, `Alert`,
`Report`, `ShareLink`, `ApiKey`, `Subscription`, `ScoreSnapshot` and a
standalone `Evidence` table are deferred to the phases that actually need
them (Phase 4 report UI, Phase 7 billing, Phase 8 monitoring).

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
| `fingerprint` | varchar(128) | Stable cross-scan identity, for the regression detection Phase 8 adds |

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

Not yet modeled (see the phase that adds them): `Project`-level UI/API
(Phase 4), `Evidence` as its own relational table (no phase commits to this
yet — object storage has sufficed so far), `CheckDefinition` (the registry
in code is the source of truth; no DB mirror exists), `ScoreSnapshot`
(Phase 8's score-history charts), `MonitorSchedule`/`Alert` (Phase 8),
`Report`/`ShareLink` (Phase 4), `ApiKey` (Phase 9's public API),
`Subscription` (Phase 7).
