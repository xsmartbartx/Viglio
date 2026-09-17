# Self-hostable image for the ARQ worker — the only process that ever
# makes an outbound request to a scan target (docs/architecture.md §3),
# and the only one that needs Playwright/Chromium (PDF report rendering,
# `render_report_pdf_job`). Same full-workspace-sync approach as
# apps/api/Dockerfile.
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

CMD ["uv", "run", "arq", "vigilo_scanner.worker.WorkerSettings"]
