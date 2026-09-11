# Vigilo

Live security and compliance scanning for AI-generated web apps.

Vigilo takes a deployed URL (or a repository), gathers evidence about it the way an
outside visitor would, runs a versioned catalogue of deterministic checks against that
evidence, and returns a prioritised, plain-language report with a paste-ready fix for
every finding. It then keeps re-running the same scan on a schedule and alerts the owner
when the result gets worse.

Built for apps shipped from Lovable, Cursor, Bolt, v0, Replit, Windsurf and Claude Code,
where the generated backend defaults — public tables, client-bundled keys, missing
headers, no legal pages — are the same handful of mistakes over and over.

---

## Why this exists

AI coding tools produce working apps faster than their authors can learn what a working
app is supposed to protect. The result is a predictable failure set:

- database rows readable by anyone with the public anon key,
- provider API keys compiled into the JavaScript bundle by a `VITE_` / `NEXT_PUBLIC_` prefix,
- staging and preview deployments left publicly reachable,
- no Content-Security-Policy, no HSTS, no rate limiting on auth routes,
- no privacy policy, no cookie consent, analytics firing on first paint in the EU.

Generic vulnerability scanners are built for hand-written enterprise software and report
hundreds of low-value findings. Vigilo runs a smaller catalogue tuned to what these
specific generators emit, and explains each result in terms the person who typed the
prompt can act on.

---

## Product surface

| Surface | What it is |
| --- | --- |
| Web app | Scan submission, live scan stream, report, score history, project management |
| Report | Shareable HTML report + PDF export + embeddable score badge |
| Monitoring | Scheduled re-scans, regression alerts, score history |
| Public API | REST + SSE, API-key authenticated, same engine as the web app |
| MCP server | `vigilo-mcp` — lets Cursor / Claude Code start scans and pull findings in-editor |
| CLI | `vigilo scan <url>` for CI pipelines and local use |

---

## Repository structure

```text
.github/
  ├─ copilot-instructions.md
  └─ agents/
       ├─ architecture.agent.md
       ├─ documentation.agent.md
       ├─ pentest.agent.md
       └─ scan-engine.agent.md        # new — owns the check catalogue
.copilot/
  └─ prompts/
       ├─ architecture.prompt.md
       ├─ documentation.prompt.md
       ├─ refactor.prompt.md
       └─ check-authoring.prompt.md   # new — authoring a single check
apps/
  ├─ web/                             # Next.js frontend
  ├─ api/                             # FastAPI control plane
  └─ scanner/                         # egress workers (isolated network zone)
packages/
  ├─ core/                            # models, validation, logging, errors
  ├─ probes/                          # evidence collectors
  ├─ checks/                          # pure check functions + manifests
  ├─ scoring/                         # deterministic score model
  ├─ reporting/                       # HTML/PDF/badge rendering
  └─ mcp/                             # MCP server
docs/
  ├─ vision.md
  ├─ architecture.md
  ├─ modules.md
  ├─ scan-engine.md
  ├─ check-catalog.md
  ├─ data-flow.md
  ├─ data-model.md
  ├─ api.md
  ├─ security.md
  ├─ build-roadmap.md
  ├─ build-workflow.md
  └─ adr/
       ├─ ADR-0001-core-architecture.md
       ├─ ADR-0002-product-scope-and-stack.md
       └─ ADR-0003-scan-authorization-model.md
brand.config.json                     # single source of truth for naming
```

---

## Architecture in one paragraph

Five layers, as defined in ADR 0001. The **Core Layer** holds models, schema-first
validation and sanitised logging. The **Modules Layer** holds the domain: probes, checks,
scoring, reporting, monitoring, integrations. The **Pipeline Layer** orchestrates scans as
queued jobs and runs CI/CD. The **Security Layer** enforces scan authorisation, egress
policy, rate governance and the audit trail. The **Documentation Layer** is this folder.

The one non-obvious decision: **probes collect evidence, checks judge evidence, and the
two never touch each other.** A probe issues network requests and writes an immutable
evidence bundle. A check is a pure function from that bundle to a finding. Every check is
therefore replayable offline, unit-testable without a network, and deterministic — the
same evidence always produces the same report. See `docs/scan-engine.md`.

---

## Branding

Every user-visible name comes from `brand.config.json`. Nothing hardcodes the product name
in source. Renaming the product is a one-file change plus a rebuild.

Alternative names held in reserve: **Prooflight**, **Latch**, **Bezpiecznik**.

---

## Security model

Vigilo sends real HTTP requests to third-party infrastructure, so authorisation is a
first-class architectural concern, not a checkbox.

- **Tier 0 (unverified)** — passive checks only. Vigilo requests exactly what a normal
  browser visiting the homepage would request. No hidden-path enumeration, no auth probing.
- **Tier 1 (verified owner)** — full active scan. Ownership is proved by DNS `TXT` record,
  a `/.well-known` token file, a meta tag, or connected repository write access.
- Never — destructive methods, credential guessing, payload fuzzing, or scanning of
  denylisted infrastructure.

See `docs/security.md` and ADR 0003.

---

## Getting started

1. Read `docs/vision.md` — what is being built and for whom.
2. Read `docs/architecture.md` and ADR 0002 — the shape and the stack.
3. Read `docs/scan-engine.md` — the core domain model.
4. Follow `docs/build-roadmap.md` — six phases, each independently shippable.

---

## Status

Design phase. No code committed yet. All documents in `/docs` are authoritative for
implementation and must be updated by the responsible agent whenever behaviour changes.

## Licence

Apache 2.0. Automated assessments only — not legal advice and not a substitute for a
manual penetration test.
