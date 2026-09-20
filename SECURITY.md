# Security policy

## Scope

This policy covers vulnerabilities **in Vigilo itself** — the control
plane (`apps/api`), scanner worker (`apps/scanner`), web app (`apps/web`),
CLI (`apps/cli`), MCP server (`apps/mcp`), and the shared `packages/*`
libraries. Examples: an authentication or authorization bypass, a way to
read another account's data, an injection vulnerability, a way to defeat
the egress guard (`docs/security.md` §1) to reach an internal address, or
a flaw in ownership verification (`docs/security.md` §4).

**Out of scope:** findings a Vigilo scan *reports about a target site*
you don't control. Vigilo is a scanning tool — a check flagging a missing
header or an exposed `.git` directory on `https://example.com` is Vigilo
working as intended, not a vulnerability in Vigilo. Report that to the
target site's own owner, not here.

Also out of scope: vulnerabilities in third-party dependencies (report
upstream), and self-inflicted issues on a self-hosted instance from
insecure configuration (e.g. skipping `docs/self-hosting.md`'s guidance).

## Reporting a vulnerability

Email **security@vigilo.io** with a description, reproduction steps, and
the affected version/commit. Encrypt anything sensitive if you'd like —
we don't currently publish a PGP key, so ask and we'll set one up.

Please don't open a public GitHub issue for a suspected vulnerability
until we've had a chance to respond.

**What to expect:**
- Acknowledgement within 3 business days.
- An initial assessment (confirmed, not reproducible, or out of scope)
  within 10 business days.
- We'll keep you updated as a confirmed issue is fixed, and credit you in
  the fix (commit message or release notes) if you'd like.

## Safe harbor

Good-faith security research against your own Vigilo account/instance —
testing auth boundaries, trying to access data you don't own, fuzzing
inputs — is welcome and won't be treated as abuse, provided you:

- Don't access, modify, or exfiltrate another account's data beyond what's
  needed to demonstrate the issue.
- Don't run denial-of-service testing against the hosted product.
- Give us a reasonable window to fix a confirmed issue before any public
  disclosure.
- Only scan targets you're authorized to scan — Vigilo's own scan-
  authorization model (`docs/security.md` §3) applies to you too.
