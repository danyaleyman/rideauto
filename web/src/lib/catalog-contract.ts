import type { SlimCar } from "@/lib/types";

export type ApiContractVersion = "v1" | "v2";

/** Версия публичного контракта каталога с API (зеркало `meta.api_version` / заголовков ответа). */
export function apiContractVersionFromMeta(
  meta: { api_version?: string } | null | undefined,
): ApiContractVersion {
  const v = String(meta?.api_version ?? "v1").trim().toLowerCase();
  return v === "v2" ? "v2" : "v1";
}

function parseIsoMs(iso: string | null | undefined): number {
  if (iso == null || iso === "") return NaN;
  const n = Date.parse(iso);
  return Number.isNaN(n) ? NaN : n;
}

/** Максимальный `catalog_updated_at` по списку slim (для ключей клиентского кэша / диагностики). */
export function maxCatalogUpdatedAtIso(cars: SlimCar[]): string | undefined {
  let best = "";
  let bestMs = -Infinity;
  for (const c of cars) {
    const iso = c.catalog_updated_at ?? null;
    const ms = parseIsoMs(iso);
    if (!Number.isNaN(ms) && ms >= bestMs) {
      bestMs = ms;
      best = iso ?? "";
    }
  }
  return best || undefined;
}
