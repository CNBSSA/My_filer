import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // `standalone` emits `.next/standalone/` with only the files the runtime
  // image needs (including a vendored server.js and the exact node_modules
  // subset). Our Dockerfile copies that directory into the final stage and
  // runs `node server.js`, keeping the production image small and startup
  // fast on Railway / ECS.
  output: "standalone",
  reactStrictMode: true,
};

export default nextConfig;
