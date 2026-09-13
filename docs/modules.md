# Modules

## Purpose

This document is the authoritative catalogue of every module in Vigilo: responsibility,
boundary, public API, dependencies and security posture. It is the reference for the
Architecture Agent, Refactor Agent and Scan Engine Agent. No module may exist without an
entry here.

Boundary rule for all modules: single responsibility, validate every input at the edge,
communicate only through the declared API, no shared mutable state, log only sanitised
data through Core.

---

## Dependency graph

```mermaid
flowchart TD
    CORE[core]
    PERSIST[persistence]
    SEC[security]
    IDENTITY[identity]
    PROJECT[project]
    PROBES[probes]
    CHECKS[checks]
    SCORING[scoring]
    REPORTING[reporting]
    INTEG[integrations]
    ORCH[orchestrator]
    MONITOR[monitoring]
    NOTIFY[notification]
    BILLING[billing]
    API[api]

    CORE --> PERSIST
    CORE --> SEC
    CORE --> IDENTITY
    CORE --> PROBES
    CORE --> CHECKS
    CORE --> SCORING
    CORE --> REPORTING
    CORE --> INTEG
    PERSIST --> SEC
    PERSIST --> IDENTITY
    PERSIST --> PROJECT
    PERSIST --> ORCH
    IDENTITY --> PROJECT
    IDENTITY --> ORCH
    PROJECT --> ORCH
    SEC --> ORCH
    PROBES --> ORCH
    CHECKS --> ORCH
    SCORING --> ORCH
    REPORTING --> ORCH
    INTEG --> PROBES
    INTEG --> ORCH
    ORCH --> API
    SEC --> API
    IDENTITY --> API
    PROJECT --> API
    MONITOR --> ORCH
    MONITOR --> NOTIFY
    BILLING --> API
```

Cycles are prohibited and enforced by an import-graph check in CI.
(`persistence`, `identity` and `project` were added in Phase 3 — see their
sections below, inserted as `1a`/`2a`/`2b` rather than renumbering the rest
of this document, since many source files already cite `docs/modules.md §N`
by number.)

---

## 1. core

**Responsibility.** Foundational primitives shared by every other module.

- Domain models (`Target`, `Scan`, `Evidence`, `Finding`, `Score`, `CheckManifest`)
- Schema-first validation primitives
- Structured, sanitised logging
- Error taxonomy and structured error objects
- Configuration and brand token loading
- Redaction utilities (secret fingerprinting)

**Boundaries.** No business logic. No network. No database access. No knowledge of any
specific check, probe or provider.

**API**

```python
validate(model, payload) -> Model            # raises ValidationError
log(event: LogEvent) -> None
error(code: ErrorCode, message: str, **ctx) -> StructuredError
redact(value: str) -> Fingerprint            # sha256 prefix + shape, never the value
config() -> Config
```

**Dependencies.** None. Root module.

**Security.** All logging passes through here, so redaction cannot be bypassed by a caller.
`redact` is the only sanctioned way any secret-shaped string enters persistent storage.

---

## 1a. persistence

**Responsibility.** The shared SQLAlchemy primitives every persistence-backed
module builds on: one declarative `Base`, the async engine/session factory,
and the Alembic migration environment.

**Boundaries.** No domain models, no business logic, no knowledge of any
specific table. Added in Phase 3 as infrastructure alongside Core, not
inside it — ADR-0001 rule 1 ("Core has no database access") stays true
because Core itself gains no new dependency; this is a separate package
that depends on Core.

**API**

```python
Base                      # declarative base every orm.py registers models against
get_engine() -> AsyncEngine
session_scope() -> AsyncContextManager[AsyncSession]   # commit-on-success, rollback-on-exception
```

**Dependencies.** core.

**Security.** None directly — it holds no domain data. Its Alembic
migrations are where the audit trail's append-only guarantee is actually
enforced (a database trigger, not application code) — see `security.md` §5.

---

## 2. security

**Responsibility.** Everything that decides whether an action against a third party is
permitted, and records that it happened.

- Scan authorisation: tier resolution, ownership proof verification
- Target denylist and SSRF guard (private ranges, IP literals, protected sectors)
- Rate governor: per-account, per-target-host, global
- Abuse heuristics: enumeration patterns, target churn, verification-bypass attempts
- Audit trail writer (append-only)

**Boundaries.** Cannot execute a probe. Cannot modify a finding. It is an authoriser and a
recorder, never an actor.

**API** (Phase 3 — `resolve_authorization`/`verify_ownership`/`audit` are real;
`check_rate` remains a Phase 6/7 placeholder, per the roadmap's scope trim —
Phase 3's `resolve_authorization()` folds a minimal, DB-derived scan-count
ceiling directly into its own inputs instead)

```python
resolve_authorization(request: AuthorizationRequest) -> AuthorizationDecision
# pure function over primitives/enums only — no ORM types, so security's
# dependency footprint below stays core + persistence, not core + project.
# The caller (an apps/api handler) loads Account/Target/OwnershipProof state
# and reduces it to AuthorizationRequest's fields first.

verify_ownership(method: VerificationMethod, origin: str, expected_nonce: str,
                  resolver=None, transport=None, txt_resolver=None) -> VerificationResult
# dns_txt | wellknown_file | meta_tag | email (email raises NotImplementedError
# in Phase 3 — needs a click-through flow that has no home before Phase 4).
# wellknown_file/meta_tag call validate_and_pin() first, same as any probe.

audit(session, event: AuditEvent) -> None
# takes an already-open session so "authorize -> audit -> create ScanJob"
# commits as one transaction, per ADR-0003's ordering requirement.
```

**Dependencies.** core, persistence. (The persistence dependency is new in
Phase 3 — a deliberate, documented expansion from core-only, since the
audit trail writer needs real DB access. Called out per the roadmap's
standing rule #2 since it's part of the authorization model.)

**Security.** Fail-closed. Any error in tier resolution downgrades to `passive` or rejects;
it never upgrades. Every decision is written to the audit trail before the scan is queued.
`verify_ownership`'s network-touching methods run inside `apps/scanner`'s ARQ worker, never
called synchronously from `apps/api` — see the ADR-0003 Phase 3 addendum.

Detail: `security.md`, ADR 0003.

---

## 2a. identity

**Responsibility.** Accounts, sessions, tenancy.

**Boundaries.** Owns `Account` persistence only. Does not verify sessions
itself for every request (`apps/api` does that via `vigilo_security`-free
JWT verification against Clerk's JWKS) — it owns the *mapping* from a
verified external identity to a local account.

**API**

```python
get_or_create_account(session, email, clerk_user_id=None) -> Account
get_account_by_id(session, account_id) -> Account | None
get_account_by_clerk_id(session, clerk_user_id) -> Account | None
```

**Dependencies.** core, persistence.

**Security.** No password/credential storage — auth is delegated entirely
to Clerk. `get_or_create_account`'s email-based linking (see
`docs/data-model.md`) is the only place two identities (anonymous email,
authenticated Clerk user) merge into one account.

---

## 2b. project

**Responsibility.** Projects, targets, ownership proofs.

**Boundaries.** Cannot perform network I/O to a target — issuing and
recording ownership proofs is pure persistence; the actual DNS/HTTP checks
live in `vigilo_security.verify_ownership`, called from `apps/scanner`.

**API**

```python
get_or_create_default_project(session, account_id) -> Project
create_target(session, project_id, origin) -> Target
get_target(session, target_id) -> Target | None
get_target_by_origin(session, project_id, origin) -> Target | None
set_opt_out(session, target_id, flag) -> None
issue_ownership_proof(session, target_id, method) -> OwnershipProof
get_ownership_proof(session, proof_id) -> OwnershipProof | None
has_valid_ownership_proof(session, target_id) -> bool
mark_proof_verified(session, proof_id) -> OwnershipProof
```

**Dependencies.** core, persistence, identity (for the `accounts.id` FK
type reference only — no runtime call into `identity`'s functions).

**Security.** `mark_proof_verified` is the only path that upgrades a
target's `verification_status`, and it's only ever called after
`vigilo_security.verify_ownership` returns `verified=True`.

---

## 3. probes

**Responsibility.** Collect evidence about a target. This is the only module permitted to
make outbound requests to a target.

Probe families:

| Probe | Collects |
| --- | --- |
| `dns` | A/AAAA/CNAME/TXT/MX records, nameservers, CAA |
| `tls` | Certificate chain, expiry, protocol versions, HTTPS enforcement |
| `http` | Response status, headers, cookies, redirect chain for a bounded path set |
| `render` | DOM after load, network waterfall, third-party origins contacted |
| `bundle` | Fetched JS/CSS assets, source-map presence, inlined configuration |
| `wellknown` | `robots.txt`, `sitemap.xml`, `security.txt`, `manifest.json` |
| `paths` | Existence of a fixed, published list of commonly exposed artefacts (Tier 1 only) |
| `subdomain` | Candidate hostnames from certificate transparency and passive DNS (Tier 1) |
| `repo` | Read-only file tree and content of a connected repository (opt-in) |

**Boundaries.** A probe records what happened. It never interprets, never assigns severity,
never imports `checks`. It cannot decide its own budget — the budget arrives in the job
envelope.

**API**

```python
run(probe_id, target, budget: RequestBudget) -> ProbeResult
seal(results: list[ProbeResult]) -> EvidenceBundle   # content-addressed, immutable
```

**Dependencies.** core, security (for the governor), integrations (for `repo`).

**Security.** Every response is size-capped and content-type-checked before parsing.
JavaScript is executed only inside the sandboxed browser context, never in the worker
process. Redaction runs before the bundle is sealed, so no unredacted secret is ever
written to storage.

---

## 4. checks

**Responsibility.** Convert evidence into findings.

A check is a pure function plus a manifest. The manifest declares identity, category,
severity, required evidence, and the remediation template. The function returns a verdict.

**Boundaries.** No I/O of any kind. No clock. No randomness. No mutation of the evidence
bundle. A check that cannot find the evidence it declared returns `inconclusive`, never
`passed`.

**API**

```python
@dataclass(frozen=True)
class CheckManifest:
    id: str                    # e.g. "VG-SEC-0101"
    category: CheckCategory
    severity: Severity
    intrusiveness: Level       # L0 passive | L1 light active
    requires: list[EvidenceKind]
    remediation: RemediationTemplate

def evaluate(evidence: EvidenceBundle) -> Verdict   # passed | failed | inconclusive | not_applicable
```

**Dependencies.** core only. This is deliberate and enforced: the import allowlist for
`packages/checks` contains `core` and the standard library.

**Security.** Findings never carry a secret value, only a fingerprint and a location.

Detail: `scan-engine.md`, catalogue: `check-catalog.md`.

---

## 5. scoring

**Responsibility.** Turn a finding set into a versioned, deterministic score and grade.

**Boundaries.** Consumes findings only. Never reads evidence. Never re-evaluates a check.
The score model is versioned; a change is a new version, never an edit.

**API**

```python
score(findings: list[Finding], model_version: str) -> ScoreResult   # 0-100, grade, breakdown
compare(previous: ScoreResult, current: ScoreResult) -> Delta
```

**Dependencies.** core.

**Security.** No user-supplied weighting. The model is fixed per version so scores cannot
be gamed by request parameters.

---

## 6. reporting

**Responsibility.** Render findings for humans: HTML report, PDF, badge, remediation prompt
text.

**Boundaries.** Cannot create, delete or reclassify a finding. The LLM writes narrative
around a finding set that is already fixed. Report generation is idempotent.

**API**

```python
build_report(scan_id) -> Report
render_pdf(report) -> bytes
render_badge(public_id) -> SVG
generate_remediation(finding, stack_profile) -> Prompt
```

**Dependencies.** core, scoring, integrations (LLM provider).

**Security.** Output validation before release: no raw evidence, no unredacted secret, no
internal identifier. If the LLM provider fails, the module falls back to the static
remediation template in the check manifest.

---

## 7. integrations

**Responsibility.** All communication with named third-party providers.

| Adapter | Purpose |
| --- | --- |
| `repo` | Read-only repository access (installation-scoped token) |
| `llm` | Report narrative and remediation prompt generation |
| `mail` | Transactional email |
| `billing` | Subscription state via merchant of record webhooks |
| `storage` | Object store reads and writes |

**Boundaries.** One adapter per provider. Business logic never talks to a provider SDK
directly. Every response is validated against a schema before it leaves the adapter.

**API**

```python
call(adapter_id, request: AdapterRequest) -> AdapterResponse
```

**Dependencies.** core.

**Security.** Provider credentials injected at runtime, never in the repository. Repository
tokens are installation-scoped and read-only. Responses are treated as untrusted input and
sanitised on the way in.

---

## 8. orchestrator

**Responsibility.** Own the lifecycle of a scan: plan, enqueue, track, assemble, finalise.

State machine:

```mermaid
stateDiagram-v2
    [*] --> queued
    queued --> authorized
    authorized --> probing
    probing --> evaluating
    evaluating --> scoring
    scoring --> reporting
    reporting --> complete
    probing --> unreachable
    probing --> failed
    evaluating --> failed
    queued --> rejected
    complete --> [*]
    unreachable --> [*]
    failed --> [*]
    rejected --> [*]
```

**Boundaries.** No probing. No check evaluation. No scoring arithmetic. It coordinates the
modules that do those things and owns the persisted scan record.

**API** (Phase 3 implements the persistence-facing half —
`create_scan_job`/`advance`/`record_scan_result`/`get_scan_by_job_id` in
`service.py` — plus the two ARQ task bodies in `jobs.py` that tie
probes+checks+scoring+integrations together and run inside `apps/scanner`.
`create_scan(account, target, mode)`/`stream(scan_id)` as a single
higher-level entry point, and the job-envelope signing below, are not yet
built — Phase 3's `apps/api` calls `create_scan_job` directly rather than
through a not-yet-existing `create_scan` wrapper.)

```python
create_scan_job(session, target_id, tier, requested_by, registry_version, budget=None) -> ScanJob
advance(session, scan_job_id, new_status) -> ScanJob   # enforces the state machine above
record_scan_result(session, job, findings, result, duration_ms, bundle_id=None) -> Scan
get_scan_by_job_id(session, job_id) -> Scan | None

# ARQ task bodies (packages/orchestrator/src/vigilo_orchestrator/jobs.py),
# registered by apps/scanner's WorkerSettings, never called from apps/api:
run_scan_job(ctx, scan_job_id: str) -> None
verify_ownership_job(ctx, proof_id: str) -> None
```

**Dependencies.** core, persistence, security, probes, checks, scoring,
integrations, identity, project. (`reporting` is dropped from this list
until Phase 5 builds it — Phase 3's report is a minimal inline HTML email,
not a `reporting`-module call.)

**Security.** Signs the job envelope handed to the scan zone. The envelope carries the
resolved tier and the request budget; a worker cannot widen its own scope. (Phase 3's
envelope is just the `scan_job_id`/`proof_id` string ARQ passes — the worker re-reads
the authorized tier from the `ScanJobRow` itself rather than trusting a signed payload;
real envelope-signing is deferred alongside request-budget enforcement, Phase 6.)

---

## 9. monitoring

**Responsibility.** Scheduled re-scans and regression detection.

**Boundaries.** Does not scan. It schedules and compares.

**API**

```python
create_monitor(project, cadence) -> Monitor
due_monitors(now) -> list[Monitor]
detect_regression(previous: Scan, current: Scan) -> RegressionReport
```

**Dependencies.** core, orchestrator, scoring.

**Security.** A monitor inherits the authorisation tier of its target and re-validates it
on every run. Ownership revocation immediately downgrades all future scheduled scans.

---

## 10. notification

**Responsibility.** Deliver alerts. Email in v1, webhook in v2.

**Boundaries.** No decision logic. It renders and delivers what monitoring produced.

**API**

```python
notify(account, event: NotificationEvent) -> DeliveryResult
```

**Dependencies.** core, integrations.

**Security.** Alert bodies contain finding titles and severities, never evidence, never a
secret fingerprint's location detail. Deep links require an authenticated session.

---

## 11. billing

**Responsibility.** Map merchant-of-record subscription state to entitlements, and enforce
quota.

**Boundaries.** Never handles card data. Never talks to a card network. Entitlement
evaluation only.

**API**

```python
entitlements(account) -> Entitlements
consume(account, meter: Meter, amount: int) -> QuotaDecision
apply_webhook(event: MoREvent) -> None
```

**Dependencies.** core, integrations.

**Security.** Webhooks are signature-verified and replay-protected. Quota is enforced
server-side at authorisation time, never in the client.

---

## 12. api

**Responsibility.** The HTTP surface: web app backend, public API, MCP backend, SSE stream.

**Boundaries.** No domain logic. Every handler validates, delegates to one module, and
serialises the result. Must never import `probes` (or `orchestrator.jobs`, or the
`scanner` app) — the control plane never makes an outbound request to a target
(`docs/architecture.md` §3), enforced by `apps/api/tests/test_no_egress_imports.py`.

**Dependencies.** All of the above except `probes` directly (reached only
transitively through `orchestrator.service`, never imported by this app's own code).

**Security.** Authentication on every route that isn't explicitly public
(`POST /v1/scans`, `GET /v1/scans/{id}` — see `api.md`). Request schema
validation before dispatch. Response schema validation before release.
Per-key rate limits (Phase 9's public API; Phase 3's session-authenticated
surface uses a minimal scan-count ceiling instead, see `security.md` §3).
Full detail: `api.md`.

---

## Final note

Any change to a module's responsibility, API or dependency list requires an update to this
document in the same change set. A pull request that alters a module boundary without
touching this file fails review.
