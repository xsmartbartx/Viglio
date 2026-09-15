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
};

export default nextConfig;
