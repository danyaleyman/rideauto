import type { NextConfig } from "next";

const apiTarget =
  process.env.WRA_API_INTERNAL?.trim().replace(/\/+$/, "") ||
  process.env.NEXT_PUBLIC_API_BASE?.trim().replace(/\/+$/, "") ||
  "http://127.0.0.1:8080";

const nextConfig: NextConfig = {
  output: "standalone",
  async redirects() {
    return [
      {
        source: "/detail/:id",
        destination: "/car/:id",
        permanent: true,
      },
    ];
  },
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${apiTarget}/api/:path*` }];
  },
};

export default nextConfig;
