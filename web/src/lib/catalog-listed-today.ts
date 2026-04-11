/** Дата «в каталоге» в часовом поясе сайта (как на сервере для nightly). */
const CATALOG_TZ = "Asia/Yekaterinburg";

function calendarDateInTz(isoMs: number, tz: string): string {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: tz,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date(isoMs));
}

/** Показать бейдж «добавлено сегодня» для строки created_at из Postgres. */
export function isCatalogListedToday(iso: string | null | undefined): boolean {
  if (iso == null || typeof iso !== "string" || !iso.trim()) return false;
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return false;
  return calendarDateInTz(t, CATALOG_TZ) === calendarDateInTz(Date.now(), CATALOG_TZ);
}
