# Self-hostable image for the control-plane API (docs/self-hosting.md,
# Phase 9). Syncs the FULL uv workspace, matching local dev's
# `uv sync --all-packages` exactly, rather than a package-scoped partial
# install — simpler and avoids a subtle path-dependency edge case, at the
# cost of some unused packages' dependencies also landing in this image.
FROM python:3.11-slim

# Pinned to the exact uv version this project is developed against —
# bump deliberately (docs.astral.sh/uv/guides/integration/docker).
COPY --from=ghcr.io/astral-sh/uv:0.11.28 /uv /uvx /bin/

WORKDIR /app
COPY . .

ENV UV_NO_DEV=1
RUN uv sync --frozen

EXPOSE 8000
CMD ["uv", "run", "uvicorn", "vigilo_api.main:app", "--host", "0.0.0.0", "--port", "8000", "--app-dir", "apps/api/src"]
