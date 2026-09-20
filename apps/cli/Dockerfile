# Standalone image for `vigilo scan` — the engine behind
# .github/actions/scan (no server, no account, no API key: the CLI runs
# the full probe->check->score pipeline in-process, see apps/cli/src's own
# module docstring). Needs Playwright/Chromium for the same reason
# apps/scanner/Dockerfile does — both call vigilo_probes.run_probes(),
# which includes the render probe. Same full-workspace-sync approach as
# apps/api/Dockerfile and apps/scanner/Dockerfile.
FROM python:3.11-slim

COPY --from=ghcr.io/astral-sh/uv:0.11.28 /uv /uvx /bin/

WORKDIR /app
COPY . .

ENV UV_NO_DEV=1
# Bare `uv sync` only installs the root project's own deps, not the
# workspace — --all-packages is required, matching local dev's own
# `uv sync --all-packages` exactly (see apps/api/Dockerfile's top comment).
RUN uv sync --frozen --all-packages
RUN uv run playwright install --with-deps chromium

ENTRYPOINT ["uv", "run", "vigilo"]
