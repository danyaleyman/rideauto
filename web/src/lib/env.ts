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
  return (process.env.NEXT_PUBLIC_API_BASE?.trim() || "http://127.0.0.1:8080").replace(
    /\/$/,
    "",
  );
}
