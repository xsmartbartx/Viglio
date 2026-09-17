import path from "node:path";
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  /* config options here */
  reactCompiler: true,
  // lib/brand.ts reads ../../../brand.config.json (the repo-wide source of
  // truth) — widen Turbopack's root beyond apps/web so that resolves.
  turbopack: {
    root: path.join(__dirname, "..", ".."),
  },
  // Self-hosting (Phase 9, docs/self-hosting.md): a standalone build only
  // copies the files `next build` actually traces as needed, small enough
  // to run without `node_modules` in the final image (Next's documented
  // Docker deployment mode). The trace itself needs the same monorepo-root
  // widening as Turbopack above, for the same brand.config.json reason —
  // Next's default tracing root is apps/web itself, which wouldn't see two
  // directories up.
  output: "standalone",
  outputFileTracingRoot: path.join(__dirname, "..", ".."),
};

export default nextConfig;
