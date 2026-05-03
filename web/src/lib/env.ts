/**
 * Канонический origin сайта (SEO, Open Graph). В проде задайте NEXT_PUBLIC_SITE_URL.
 */
export function getSiteUrl(): string {
  const u = process.env.NEXT_PUBLIC_SITE_URL?.trim();
  if (u) return u.replace(/\/+$/, "");
  return "https://rideauto.ru";
}

/**
 * Серверные запросы (SSR) идут на внутренний базовый URL API.
 * Клиентские — на публичный (доступный из браузера).
 */
export function getServerApiBase(): string {
  const internal = process.env.WRA_API_INTERNAL?.trim();
  if (internal) return internal.replace(/\/$/, "");
  const pub = process.env.NEXT_PUBLIC_API_BASE?.trim();
  if (pub) return pub.replace(/\/$/, "");
  return "http://127.0.0.1:8080";
}

/**
 * Базовый origin для вызовов API из браузера (клиентский бандл).
 * Пустая строка: относительные URL `/api/...` — Next проксирует на `WRA_API_INTERNAL` (см. `next.config.ts`).
 * Задайте полный URL только если API на другом origin (CORS/отдельный домен).
 */
export function getPublicApiBase(): string {
  const pub = process.env.NEXT_PUBLIC_API_BASE?.trim();
  if (!pub || pub === "same-origin") return "";
  return pub.replace(/\/$/, "");
}
