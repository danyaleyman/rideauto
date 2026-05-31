/** Инженерные подсказки (Docker, WRA_API_INTERNAL) — только dev/staging, не для покупателей. */
export function showCatalogEngineeringNotices(): boolean {
  return process.env.NODE_ENV !== "production";
}
