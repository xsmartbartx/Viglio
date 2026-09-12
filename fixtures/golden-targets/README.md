# Golden-target fixtures

Hand-authored `EvidenceBundle` JSON, used by `apps/cli/tests/test_determinism.py`
to prove checks+scoring are deterministic and that a worse configuration scores
meaningfully lower — without any network I/O (docs/architecture.md §11).

- `good-config.json` — every Phase 1 check should pass.
- `bad-config.json` — deliberately synthetic: it combines a plaintext-only
  `http.url` (to fail `VG-TLS-001`, HTTPS enforcement) with a fully-populated,
  weak/expired `tls` observation (to also fail `VG-TLS-003/004/005/007/008`).
  Today's `vigilo_probes` orchestrator would never actually produce this exact
  combination — it only attempts a TLS probe when the final URL is `https://`.
  That's fine: these fixtures exercise the checks/scoring layer in isolation
  from the probe layer, and this combination is a legitimate `EvidenceBundle`
  as far as that layer is concerned. Do not "fix" it to match orchestrator
  behavior without also reconsidering whether it still stresses enough checks.

Certificate dates in both fixtures are chosen so the fixtures don't silently
go stale: `good-config.json` uses `not_after: 2099-...` (always in the future
for the foreseeable lifetime of this repo); `bad-config.json` uses a date
already in the past. `days_until_expiry` is a static field the checks read
directly — it is not recomputed from `not_after` at evaluation time, so it
won't drift either.
