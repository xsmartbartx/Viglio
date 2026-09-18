# Self-hosting

## Purpose

Phase 9 (`docs/build-roadmap.md`) ships three container images —
`apps/api`, `apps/scanner`, `apps/web` — plus `docker-compose.self-host.yml`
to run them alongside their infrastructure (Postgres, Redis, MinIO). This
is the same application that runs as the hosted product, packaged for an
operator who wants to run it on their own infrastructure instead.

This is a self-managed deployment, not a managed one: you own upgrades,
backups, TLS termination, and the Clerk/Paddle/Postmark/Anthropic accounts
those integrations call out to.

## Requirements

- Docker and Docker Compose (v2, the `docker compose` subcommand).
- A [Clerk](https://clerk.com) application — `apps/web` and `apps/api` must
  point at the *same* Clerk application, and it needs a JWT template (any
  name) that adds an `email` claim (`apps/api`'s `require_account()` reads
  it on first sign-in).
- Optional, each fails loudly rather than silently no-opping if you enable
  a feature that needs it without configuring it:
  - [Postmark](https://postmarkapp.com) — free-scan report emails and
    ownership-verification instructions. Scans complete and reports render
    without it.
  - [Anthropic](https://console.anthropic.com) — LLM-backed remediation
    prompts. Reports render with template-based remediation text without
    it (`docs/adr/ADR-0004-llm-boundary.md`'s hard availability
    requirement).
  - [Paddle](https://paddle.com) — checkout and subscription billing.
    Every account defaults to the Free plan's entitlements without it;
    the checkout endpoint raises a clear config error if called with it
    unset, since unlike email/LLM there's no safe fallback for processing
    a payment.

## Quick start

```bash
git clone <this repository> && cd vigilo
cp .env.example .env
# Edit .env: at minimum set CLERK_SECRET_KEY, CLERK_JWKS_URL,
# NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY, and NEXT_PUBLIC_CLERK_JWT_TEMPLATE.

docker compose -f docker-compose.self-host.yml up -d --build

# First run only — creates the schema.
docker compose -f docker-compose.self-host.yml exec api \
  uv run alembic -c packages/persistence/alembic.ini upgrade head
```

`apps/web` is now at `http://localhost:3000`, `apps/api` at
`http://localhost:8000` (`/healthz`, `/docs`).

## Environment variables

`docker-compose.self-host.yml` wires Postgres/Redis/MinIO's internal
addresses for you — you only need to set the variables in `.env.example`'s
`PADDLE_*`/`CLERK_*`/`POSTMARK_*`/`ANTHROPIC_*` sections, plus these three
build-time variables that `apps/web`'s image needs (see below):

| Variable | Used by | Notes |
|---|---|---|
| `CLERK_SECRET_KEY` | api, web | Required — server-side session verification. |
| `CLERK_JWKS_URL` | api | Required — `require_account()`'s JWT verification. |
| `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` | web (build arg) | Required. |
| `NEXT_PUBLIC_CLERK_JWT_TEMPLATE` | web (build arg) | Defaults to `vigilo-api`. |
| `PUBLIC_API_BASE_URL` | web (build arg) | The api's public origin, e.g. `https://api.yourdomain.com`. Defaults to `http://localhost:8000`, only correct for a single-machine trial. |
| `POSTGRES_PASSWORD` | postgres, api, scanner | Defaults to a dev placeholder — set a real one. |
| `OBJECT_STORE_SECRET_KEY` | minio, api, scanner | Same. |
| `POSTMARK_SERVER_TOKEN`, `MAIL_FROM_ADDRESS` | api, scanner | Optional (see above). |
| `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL` | api, scanner | Optional (see above). |
| `PADDLE_VENDOR_ID`, `PADDLE_WEBHOOK_SECRET`, `PADDLE_PRICE_ID_BUILDER`, `PADDLE_PRICE_ID_STUDIO`, `PADDLE_PRICE_ID_BUSINESS` | api | Optional (see above). One price ID per paid plan tier. |
| `WEB_APP_URL` | api, scanner | The web app's origin — `apps/scanner`'s ARQ worker navigates here with Playwright to render a scan's report page to PDF. Must be `https://` + `WEB_DOMAIN` in production (see below); apps/api's CORS check is an exact origin-string match. |
| `WEB_DOMAIN`, `API_DOMAIN` | caddy | Production only — see "Production VPS deployment" below. Leave unset for local-only self-hosting. |

**Build-time vs. runtime**: `NEXT_PUBLIC_*` variables are inlined into
`apps/web`'s JavaScript bundle by `next build` — they cannot be changed by
editing environment variables on an already-built container, only by
rebuilding (`docker compose -f docker-compose.self-host.yml build web`
after changing `.env`).

## Production VPS deployment

The Quick Start above binds `apps/web`/`apps/api` to `127.0.0.1` only —
fine for a single-machine trial, not reachable from the internet. For a
real deployment with a domain and TLS, `docker-compose.self-host.yml`
includes a `caddy` service that terminates HTTPS (automatic Let's Encrypt
certificates, zero extra config) and is the only service bound to a public
port (`80`/`443`).

**What you need to do yourself** (none of this is something an assistant
can do on your behalf — it's account creation, purchases, and DNS you
control):

1. Provision a VPS (any provider) with a public IP and Docker installed.
2. Buy a domain if you don't have one, and point two DNS **A records** at
   the VPS's IP: one for the app (e.g. `app.yourdomain.com`), one for the
   API (e.g. `api.yourdomain.com`). Caddy needs both — the public REST API
   (`docs/api.md`) is served from its own origin, not a path under the app.
3. Make sure ports `80` and `443` are reachable (most VPS providers allow
   this by default; check any separate cloud firewall/security-group rules).
4. Clone the repo onto the VPS, `cp .env.example .env`, and fill in real
   values — `WEB_DOMAIN`/`API_DOMAIN` (the two hostnames from step 2),
   `PUBLIC_API_BASE_URL`/`WEB_APP_URL` set to their `https://` form, and
   every account credential from "Requirements" above (a **production**
   Clerk application, not the dev instance used for local testing — plus
   real Paddle/Postmark/Anthropic credentials if you're using them).

**Then run the deploy script:**

```bash
./scripts/deploy.sh
```

This builds the images, starts the full stack (including `caddy`), and
brings the schema to head — safe to re-run for every future update too
(it's the same `git pull && up -d --build && alembic upgrade head`
sequence as "Updating" below, just as one command). First startup can take
up to a minute while Caddy requests its initial certificates from Let's
Encrypt; watch progress with `docker compose -f docker-compose.self-host.yml
logs -f caddy`.

## Updating

```bash
./scripts/deploy.sh
```

Or the three commands it runs, individually:

```bash
git pull
docker compose -f docker-compose.self-host.yml up -d --build
docker compose -f docker-compose.self-host.yml exec api \
  uv run alembic -c packages/persistence/alembic.ini upgrade head
```

## Custom domains for white-labeled reports (Business plan)

A Business-tier account's `BrandingProfile` (`PUT /v1/me/branding-profile`)
carries an optional `custom_domain` field. This is a different concern
from `WEB_DOMAIN`/`API_DOMAIN` above (your own app's domain) — it's a
*customer's* domain for their own white-labeled reports. Vigilo does not
provision DNS or TLS certificates for it — that would be a materially
larger, per-account infrastructure undertaking outside this phase's scope.
If you want to support it, point that domain's DNS at your `apps/web`
deployment yourself and add its own site block to the bundled `Caddyfile`
(or your own reverse proxy); the `custom_domain` field itself is
presentation metadata Vigilo stores and returns on report/share-link
responses, not something it actively redirects or routes.

## Backups

`vigilo_self_host_postgres_data` and `vigilo_self_host_minio_data`
(Docker named volumes) hold everything stateful — scan history, findings,
accounts, and stored evidence. Back these up the way you back up any
Docker volume (e.g. `docker run --rm -v vigilo-self-host_vigilo_self_host_postgres_data:/data ...`
into a tarball on a schedule); there is no built-in backup job.

## CI coverage

`.github/workflows/ci.yml`'s `docker-build` job builds all three images
(no push) on every PR, catching a broken Dockerfile before it merges —
it does not exercise `docker-compose.self-host.yml` itself, which is
verified manually per `docs/build-roadmap.md`'s Phase 9 entry.
