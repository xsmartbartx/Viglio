# Golden-target fixtures

Hand-authored `EvidenceBundle` JSON, used by `apps/cli/tests/test_determinism.py`
to prove checks+scoring are deterministic and that a worse configuration scores
meaningfully lower — without any network I/O (docs/architecture.md §11).

- `good-config.json` — every one of the 57 v0.1 checks should pass (score
  100, grade A): full security headers, modern verified TLS, safe cookies,
  linked legal documents, an integrity-pinned third-party script, all
  `.well-known` paths present, no detected backends.
- `bad-config.json` — deliberately synthetic and deliberately excessive: it
  fails 49 of 57 checks (score 0, grade F), including a planted Supabase
  service-role key (`VG-DAT-001`, the product's flagship check per
  `docs/vision.md`), an introspectable Supabase anon-key schema, an open
  Firebase Realtime Database, a publicly listable S3 bucket, and a fetched
  script carrying one example of every `CLI` category secret pattern. It
  also combines a plaintext-only `http.url` (to fail `VG-TLS-001`, HTTPS
  enforcement) with a fully-populated, weak/expired `tls` observation (to
  also fail `VG-TLS-003/004/005/007/008`) — a combination today's
  `vigilo_probes` orchestrator would never actually produce on its own (it
  only attempts a TLS probe when the final URL is `https://`). That's fine:
  these fixtures exercise the checks/scoring layer in isolation from the
  probe layer, and every field here is a legitimate `EvidenceBundle` as far
  as that layer is concerned. Do not "fix" it to match orchestrator behavior
  without also reconsidering whether it still stresses enough checks.

Certificate dates in both fixtures are chosen so the fixtures don't silently
go stale: `good-config.json` uses `not_after: 2099-...` (always in the future
for the foreseeable lifetime of this repo); `bad-config.json` uses a date
already in the past. `days_until_expiry` is a static field the checks read
directly — it is not recomputed from `not_after` at evaluation time, so it
won't drift either.
