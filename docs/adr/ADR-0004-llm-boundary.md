# ADR-0004: LLM boundary

| Field | Value |
| --- | --- |
| Status | Accepted; implemented (Phase 5) |
| Date | 2026-09-15 |

## Context

`docs/prooflight-vision-and-architecture.md` §23's ADR table names this
decision explicitly: "`ADR-0008` | LLM boundary — what the model may and may
not decide | Blocks Phase 5." Phase 5 (`docs/build-roadmap.md`) adds
Claude-backed, per-finding remediation prose — the first place an LLM
touches Vigilo's pipeline at all. This ADR records the boundary before any
LLM code ships, per the same standing rule that put ADR-0003 in place
before `resolve_authorization()` was written. (Numbered `0004`, not `0008`
— the Prooflight doc's numbering assumed a longer ADR sequence than this
repository has actually needed so far; `docs/adr/` numbers sequentially by
actual creation order, not by the draft's aspirational numbering.)

`docs/build-roadmap.md`'s existing Phase 5 paragraph cites "strictly
additive per ADR-0001 rule 2" — checked against `docs/adr/ADR-0001-core-
architecture.md`, whose actual rule 2 is "probes collect evidence; checks
judge evidence; the two never import each other," an unrelated boundary.
That citation was wrong; this ADR is what the roadmap should have pointed
at, and `docs/build-roadmap.md` is corrected in the same change set that
adds this file.

## Decision

**The LLM never influences a number.** It cannot set or change a score,
grade, severity, confidence, or verdict. Those are already fully decided —
by `packages/checks`' pure functions and `packages/scoring`'s deterministic
algorithm — before an LLM is ever called. The LLM only attaches
explanatory prose (`explanation`, `impact`, `remediation_steps`,
`agent_prompt`, `estimated_effort`) to a finding that already exists in its
final form, matching `docs/prooflight-vision-and-architecture.md` §9's own
framing exactly. It cannot create, delete, reclassify or re-rank a finding.

**Template fallback is a hard availability requirement, not a preference.**
If `ANTHROPIC_API_KEY` is unset, the provider call fails, or the response
fails schema validation, the report renders `packages/checks`' existing
static `remediation_template` text instead — deterministically, for every
finding, every time. A scan's completion, and a report's ability to render,
never depend on LLM availability. This is verified live, not just unit
tested: Phase 5's verification pass runs a real scan with
`ANTHROPIC_API_KEY` unset and confirms every finding shows
`source: "template"`.

**Redaction is allowlist-based, not a runtime scanner.**
`vigilo_core.redact.redact()` fingerprints a *known* secret value — it has
no "does this text look secret-shaped" detector, so it cannot gate
arbitrary prompt content. Instead, the prompt-construction call site
(`vigilo_reporting.remediation.generate_remediation()`) only ever reads
from an explicit, reviewed allowlist of fields already known to be
redaction-safe: `finding.title`, `finding.summary`, `finding.severity`,
`manifest.description`, `manifest.category`, and
`finding.evidence.matched_indicator` when present (guaranteed
redaction-safe by construction — every secret-detecting check already
routes through `redact()` before a value ever becomes a
`CheckResult.matched_indicator`, per `docs/data-model.md`'s `findings`
table notes). **`target_origin` is never sent to the LLM at all** — not
tokenized, simply omitted, which is a stronger guarantee than
`docs/prooflight-vision-and-architecture.md` §9.2 step 4's own "tokenize
the domain" suggestion. The raw evidence bundle (object storage) is never
read by this code path; only the already-persisted, already-redacted
`Finding`/`Evidence` fields are in scope.

**The LLM's response is strict JSON, validated and discarded whole on any
failure — never partially parsed.** `vigilo_integrations.llm` validates
only the HTTP/transport-level response shape (a 2xx with text content).
`vigilo_reporting.remediation.generate_remediation()` then parses that text
as JSON and validates it against `RemediationPrompt`'s Pydantic schema. Any
parse error, missing field, or type mismatch discards the entire response
and falls back to the template — never a "best effort" partial result
built from a malformed response.

**Known, deliberately-scoped residual risk: prompt injection via untrusted
finding content.** A finding's `summary`/`matched_indicator` ultimately
derives from a real HTTP response the *scanned target* controls — not a
trusted first-party source. A malicious or compromised target could in
principle craft response content designed to hijack the remediation
prompt, and `agent_prompt` in particular is explicitly meant to be pasted
into a user's own AI coding tool — a real downstream execution context, not
just displayed text. This is not fully mitigated here. Two structural
backstops exist — the strict-JSON-validate-or-discard rule above, and an
explicit instruction in the system/developer-level prompt telling the model
to treat finding/evidence content as untrusted data to describe, never as
instructions to follow — but neither is a complete defense against a
sufficiently crafted payload that still produces well-formed JSON. Recorded
here as a known gap, not silently ignored or overclaimed as solved;
revisit if it manifests as a real incident rather than a theoretical one.

**EU-boundary domain tokenization (§9.2 step 4) is explicitly deferred, not
implemented.** `accounts.data_region` remains an unused placeholder column
(`docs/data-model.md`) — no data-residency infrastructure exists yet to
make tokenization meaningful. Omitting `target_origin` from the prompt
entirely (above) covers the redaction concern this phase actually needs;
region-aware routing is a separate, larger piece of infrastructure this
ADR does not attempt to retrofit.

## Consequences

- `packages/reporting.build_report()` never calls the LLM path directly and
  never awaits anything — it only reads already-cached `RemediationPrompt`
  results a caller passes in, falling back to
  `template_remediation()` (pure, synchronous) for any finding without one.
  This is what keeps a report render fast and available regardless of LLM
  latency or an outage — see `docs/build-roadmap.md`'s Phase 5 entry for
  the mechanism (a background job, not an inline call).
- Every future LLM-touching feature in Vigilo (Phase 8's monitoring
  narrative, if any; a future chat-style assistant) inherits this same
  boundary by default unless a new ADR explicitly revisits it: no numeric
  authority, allowlist-based redaction, strict-schema-or-discard, and an
  explicit disclosed residual-risk note for any new untrusted-input surface
  it introduces.

## References

`docs/prooflight-vision-and-architecture.md` §9 (Analysis layer), §23
(ADR table); `docs/adr/ADR-0001-core-architecture.md`; `docs/build-
roadmap.md` Phase 5; `docs/data-model.md` (`findings`, `remediation_cache`).
