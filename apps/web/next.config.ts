import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "export",
  basePath: "/My_filer",
  trailingSlash: true,
  reactStrictMode: true,
  images: {
    unoptimized: true,
  },
};

export default nextConfig;
