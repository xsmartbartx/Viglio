# Product Vision

## Purpose

This document defines what Vigilo is, who it serves, what it deliberately does not do, and
how it is expected to make money. It is the reference for scope decisions. Any feature
proposal that cannot be traced to a section here should be rejected or should first amend
this document.

---

## 1. Problem statement

A new class of application is being deployed by people who did not write, and often cannot
read, the code that runs it. The generator produces something that works on first load.
It does not produce something that is safe to expose to the public internet.

The failures are not random. Across the tools in this category the same defaults recur:

| Failure | Root cause |
| --- | --- |
| Database readable by anyone | Row-level security off by default; anon key shipped to the client |
| Provider API keys in the JS bundle | Build tools inline any variable with a public prefix |
| Staging / preview environments public | Preview deploys get real URLs and no access control |
| No CSP, HSTS, frame protection | Generators emit application code, not platform configuration |
| No rate limiting on auth routes | Auth is scaffolded, not hardened |
| No privacy policy or cookie consent | Legal obligations are invisible to the person prompting |

The author of the app has no vocabulary for these problems, no tooling habit, and usually
no budget for a penetration test. They find out when a bill arrives from an API provider,
or when their user table appears on a forum.

## 2. Users

**Primary — the solo shipper.** One person, one product, deployed from a browser-based
generator. Non-technical or semi-technical. Needs to know *what is broken, how bad it is,
and exactly what to paste back into the tool that built it.*

**Secondary — the agency / freelancer.** Ships client sites built the same way. Needs
repeatable audits, branded reports, and multiple workspaces. Highest willingness to pay.

**Tertiary — the small engineering team.** Has real engineers but no security function.
Needs the API, the CLI and CI integration more than the dashboard.

**Explicitly not the user.** Enterprises with an existing AppSec programme. They have
tools, budget, and requirements Vigilo will not meet. Do not build for them.

## 3. Value proposition

> Vigilo tells you, in five minutes and in plain language, what a stranger can see or take
> from the app you just deployed — and gives you the exact prompt to fix it.

Three things carry the product:

1. **Evidence, not inference.** Findings are backed by a recorded request and response.
   The report shows what was asked and what came back. No "possible" findings.
2. **Remediation in the user's medium.** The fix is a prompt written for the generator that
   produced the problem, not a CVE reference and a link to a standards document.
3. **Continuity.** A scan is a snapshot of one deploy. The product's durable value is the
   scheduled re-scan that catches the regression the fifth deploy reintroduced.

## 4. Differentiation

| Vector | Generic scanners | Vigilo |
| --- | --- | --- |
| Check selection | Broad OWASP coverage, high noise | Narrow catalogue tuned to generator defaults |
| Output audience | Security engineer | The person who wrote the prompt |
| Remediation | Advisory text | Paste-ready prompt for the exact stack detected |
| Cadence | On demand | Scheduled, with regression alerting |
| Legal layer | Out of scope | Privacy policy, consent, retention, accessibility |

The moat is not the scanning technology, which is commodity. It is the curated catalogue
plus the fix corpus: every check carries a remediation template written and revised against
real generator output. That corpus compounds and cannot be scraped from a CVE feed.

## 5. Scope

### In scope

- Unauthenticated, non-destructive assessment of a live HTTP target.
- Optional read-only source analysis of a connected repository or uploaded archive.
- Deterministic scoring, versioned so historical scores remain comparable.
- Scheduled re-scans, regression detection, notification.
- Report distribution: shareable link, PDF, embeddable badge.
- Programmatic access: REST API, CLI, MCP server.

### Out of scope (v1)

- Authenticated scanning of logged-in application state.
- Any check that mutates target state, guesses credentials, or sends attack payloads.
- Continuous runtime protection, WAF, or agent-in-production.
- Mobile or native binaries.
- Legal *advice*. Vigilo detects the absence of a document; it does not draft or bless one.

### Never in scope

- Scanning a target whose owner has not been identified, beyond the passive tier.
- Storing or displaying any secret value discovered during a scan (fingerprint only).
- Selling, publishing or leaderboarding a target's findings without explicit opt-in.

## 6. Guiding principles

1. **Deterministic over clever.** Same evidence, same report. A score that moves without a
   deploy destroys the product's credibility.
2. **Evidence or silence.** If a finding cannot be shown, it is not reported.
3. **Safe by default.** The intrusive path requires proof of ownership. The default path is
   indistinguishable from a browser visit.
4. **Legible output.** Every string a user reads is written for someone who has never heard
   of a security header.
5. **Small catalogue, high precision.** Ten checks that are always right beat two hundred
   that are usually right. False positives are treated as incidents.

## 7. Business model

Subscription, three tiers, differentiated by project count, scan volume, monitoring
frequency and access to the deeper modules (repository scan, subdomain discovery, branded
reports).

| Tier | Target user | Gate |
| --- | --- | --- |
| Solo | Single-app shipper | 1 project, weekly monitoring |
| Studio | Indie / multi-project | 5 projects, daily monitoring, repository scan, API |
| Agency | Freelancer / agency | 25 projects, white-label reports, client workspaces, SLA |

Free tier: one passive scan per target, first finding revealed, remainder gated. The free
scan is the acquisition mechanism and must stay genuinely useful.

Billing runs through a merchant of record (Paddle or Lemon Squeezy) rather than direct card
processing, so EU VAT, invoicing and consumer-withdrawal handling are outsourced. See
ADR 0002.

## 8. Success criteria

| Horizon | Criterion |
| --- | --- |
| Phase 1 | A passive scan of an arbitrary public URL returns a scored report in under 30s |
| Phase 2 | A verified owner receives an active scan with reproducible evidence per finding |
| Phase 3 | A regression introduced by a deploy is detected and alerted within one cycle |
| Phase 4 | Median finding is fixed by pasting the supplied prompt, without further research |
| Ongoing | False-positive rate under 2% of surfaced findings, measured on a labelled corpus |

## 9. Risks

| Risk | Response |
| --- | --- |
| Being used to scan sites the user does not own | Tiered authorisation, ownership proof, denylist, audit trail (ADR 0003) |
| Egress IPs blocklisted or rate-limited by hosts | Fixed egress pool, published IP list and User-Agent, conservative request budget |
| False positives destroying trust | Evidence requirement, labelled regression corpus in CI, catalogue versioning |
| Generators fix their defaults, checks go stale | Catalogue is versioned and continuously re-validated against fresh generator output |
| Liability for a missed vulnerability | Contractual scope limits, no certification language, explicit non-advice disclaimer |
| Category commoditised by the generators themselves | Move value to monitoring, cross-tool coverage and the remediation corpus |

## 10. Non-goals for the first year

- No self-hosted or on-premise deployment.
- No SOC 2 / ISO certification programme.
- No marketplace of third-party checks.
- No human-review service until automated precision is proven.

---

## Final note

Vigilo is a narrow product deliberately. Its defensibility comes from knowing one class of
application extremely well. Every scope expansion should be tested against that: does this
make the product better at the thing it is uniquely good at, or merely bigger?
