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

export function getPublicApiBase(): string {
  // Для браузера безопасный дефолт — same-origin (/api через текущий домен),
  // иначе в проде можно случайно уйти на localhost пользователя.
  return (process.env.NEXT_PUBLIC_API_BASE?.trim() || "").replace(/\/$/, "");
}
