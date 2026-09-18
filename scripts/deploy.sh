#!/usr/bin/env bash
# Redeploy the self-hosted stack on a production VPS
# (docs/self-hosting.md's "Production VPS deployment" section). Idempotent
# — safe to re-run for every update, not just the first deploy: pulls the
# latest commit, rebuilds any changed images, restarts the stack, and
# brings the schema to head.
#
# Run from anywhere inside the repo; assumes docker-compose.self-host.yml
# is already configured via .env (see .env.example) and the stack has been
# started at least once (`docker compose -f docker-compose.self-host.yml
# up -d --build`) so `api` exists to run migrations against.
set -euo pipefail
cd "$(dirname "$0")/.."

git pull
docker compose -f docker-compose.self-host.yml up -d --build
docker compose -f docker-compose.self-host.yml exec -T api \
  uv run alembic -c packages/persistence/alembic.ini upgrade head
