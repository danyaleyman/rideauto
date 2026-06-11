import type { NextConfig } from "next";
import createBundleAnalyzer from "@next/bundle-analyzer";

const apiTarget =
  process.env.WRA_API_INTERNAL?.trim().replace(/\/+$/, "") ||
  process.env.NEXT_PUBLIC_API_BASE?.trim().replace(/\/+$/, "") ||
  "http://127.0.0.1:8080";

const cspEnforce =
  process.env.CSP_ENFORCE === "1" || process.env.NEXT_PUBLIC_CSP_ENFORCE === "1";
const isProd = process.env.NODE_ENV === "production";

// `unsafe-eval` нужен только dev-сборке (webpack/turbopack eval source maps).
// В enforce-режиме (prod) убираем его; `unsafe-inline` для script остаётся до перехода
// на nonce-CSP (см. TODO: middleware nonce injection) — иначе Next App Router ломается.
const scriptSrc = ["'self'", "'unsafe-inline'", cspEnforce ? null : "'unsafe-eval'"]
  .filter(Boolean)
  .join(" ");

const imgSrc = cspEnforce
  ? "img-src 'self' https: data: blob:"
  : "img-src 'self' https: http: data: blob:";

const cspDirectives = [
  "default-src 'self'",
  `script-src ${scriptSrc}`,
  "style-src 'self' 'unsafe-inline'",
  imgSrc,
  "connect-src 'self' https:",
  "font-src 'self' data:",
  "object-src 'none'",
  "worker-src 'self' blob:",
  "manifest-src 'self'",
  "frame-src 'self'",
  "frame-ancestors 'self'",
  "base-uri 'self'",
  "form-action 'self'",
  ...(cspEnforce && isProd ? ["upgrade-insecure-requests"] : []),
]
  .filter(Boolean)
  .join("; ");

const securityHeaders = [
  { key: "X-Frame-Options", value: "DENY" },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  {
    key: "Permissions-Policy",
    value: "camera=(), microphone=(), geolocation=()",
  },
  {
    key: cspEnforce ? "Content-Security-Policy" : "Content-Security-Policy-Report-Only",
    value: cspDirectives,
  },
];

const nextConfig: NextConfig = {
  output: "standalone",
  transpilePackages: ["three", "@react-three/fiber", "@react-three/drei"],
  async headers() {
    return [
      {
        source: "/:path*",
        headers: securityHeaders,
      },
    ];
  },
  images: {
    // Картинки рендерятся с `unoptimized` (грузятся напрямую или через same-origin /api/images),
    // поэтому оптимизатор Next и remotePatterns по факту не задействованы. Список держим явным
    // (allowlist CDN, зеркалит backend WRA_IMAGE_ALLOWED_HOSTS) — на случай включения оптимизации.
    remotePatterns: [
      { protocol: "https", hostname: "*.encar.com" },
      { protocol: "https", hostname: "encar.com" },
      { protocol: "https", hostname: "*.autoimg.cn" },
      { protocol: "https", hostname: "autoimg.cn" },
      { protocol: "https", hostname: "*.che168.com" },
      { protocol: "https", hostname: "che168.com" },
      { protocol: "https", hostname: "*.byteimg.com" },
      { protocol: "https", hostname: "*.bytecdn.com" },
      { protocol: "https", hostname: "*.dcarimg.com" },
      { protocol: "https", hostname: "images.unsplash.com" },
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
      { source: "/about", destination: "/", permanent: true },
      { source: "/about.html", destination: "/", permanent: true },
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
      { source: "/catalog-encar.html", destination: "/catalog", permanent: true },
      { source: "/catalog/encar", destination: "/catalog", permanent: true },
      { source: "/catalog/korea", destination: "/catalog", permanent: true },
      { source: "/catalog/che168", destination: "/catalog?region=china", permanent: true },
      { source: "/catalog/china", destination: "/catalog?region=china", permanent: true },
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
