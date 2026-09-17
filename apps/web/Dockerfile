# Self-hostable image for the web frontend (docs/self-hosting.md, Phase 9).
# Multi-stage: the build stage produces Next.js's "standalone" output
# (next.config.ts's output: "standalone" — small enough to run without
# node_modules, per Next's documented Docker deployment mode), the runtime
# stage just runs it.
#
# NEXT_PUBLIC_* vars are inlined into the JS bundle at build time — that's
# Next.js's own behavior, not something this image's runtime env can change
# later. Override them with --build-arg if self-hosting under a different
# Clerk application or API origin than the defaults below.
FROM node:22-slim AS builder

WORKDIR /app
# Full monorepo context, not just apps/web: lib/brand.ts imports
# ../../../brand.config.json, and next.config.ts's outputFileTracingRoot
# points at the repo root for the same reason (see that file's comment).
COPY . .

ARG NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
ARG NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY
ARG NEXT_PUBLIC_CLERK_JWT_TEMPLATE=vigilo-api
ENV NEXT_PUBLIC_API_BASE_URL=$NEXT_PUBLIC_API_BASE_URL \
    NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=$NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY \
    NEXT_PUBLIC_CLERK_JWT_TEMPLATE=$NEXT_PUBLIC_CLERK_JWT_TEMPLATE

WORKDIR /app/apps/web
RUN npm ci
RUN npm run build

FROM node:22-slim AS runner

ENV NODE_ENV=production \
    PORT=3000 \
    HOSTNAME=0.0.0.0

WORKDIR /app

# `next build` writes .next relative to its CWD (apps/web), not the
# outputFileTracingRoot — but outputFileTracingRoot nests the standalone
# output's own internal layout under its monorepo-relative path
# (.next/standalone/apps/web/server.js, not .../standalone/server.js), same
# reasoning as next.config.ts's comment. .next/static and public/ aren't
# part of the trace and must be copied in by hand (Next's own documented
# instruction).
COPY --from=builder /app/apps/web/.next/standalone ./
COPY --from=builder /app/apps/web/.next/static ./apps/web/.next/static
COPY --from=builder /app/apps/web/public ./apps/web/public

EXPOSE 3000
CMD ["node", "apps/web/server.js"]
