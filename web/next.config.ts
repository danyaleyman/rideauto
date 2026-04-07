import type { NextConfig } from "next";
import createBundleAnalyzer from "@next/bundle-analyzer";

const apiTarget =
  process.env.WRA_API_INTERNAL?.trim().replace(/\/+$/, "") ||
  process.env.NEXT_PUBLIC_API_BASE?.trim().replace(/\/+$/, "") ||
  "http://127.0.0.1:8080";

const nextConfig: NextConfig = {
  output: "standalone",
  images: {
    remotePatterns: [
      {
        protocol: "https",
        hostname: "**",
      },
      {
        protocol: "http",
        hostname: "**",
      },
    ],
    formats: ["image/avif", "image/webp"],
  },
  async redirects() {
    return [
      {
        source: "/detail/:id",
        destination: "/car/:id",
        permanent: true,
      },
      { source: "/index.html", destination: "/", permanent: true },
      { source: "/about.html", destination: "/about", permanent: true },
      { source: "/howtobuy.html", destination: "/buy", permanent: true },
      { source: "/contacts.html", destination: "/contacts", permanent: true },
      { source: "/privacy.html", destination: "/privacy", permanent: true },
      { source: "/cookies.html", destination: "/cookies", permanent: true },
      { source: "/agreement.html", destination: "/agreement", permanent: true },
      {
        source: "/catalog-che168.html",
        destination: "/catalog?region=china",
        permanent: true,
      },
    ];
  },
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${apiTarget}/api/:path*` }];
  },
};

const withBundleAnalyzer = createBundleAnalyzer({
  enabled: process.env.ANALYZE === "true",
});

export default withBundleAnalyzer(nextConfig);
