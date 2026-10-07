import type { Market } from "@/lib/catalog-url";

/** Внутренний source API (БД/Meili). Не показываем в браузерных URL. */
export function marketToApiSource(market: Market): "encar" | "che168" | "autotrader" {
  if (market === "china") return "che168";
  if (market === "usa") return "autotrader";
  return "encar";
}

/** Legacy query/path → рынок каталога. */
export function legacySourceToMarket(raw: string | null | undefined): Market | null {
  const s = (raw ?? "").trim().toLowerCase();
  if (s === "china" || s === "che168") return "china";
  if (s === "usa" || s === "autotrader") return "usa";
  if (s === "korea" || s === "encar") return "korea";
  return null;
}

/** Сегмент пути `/catalog/:segment` → рынок (для 301). */
export function catalogPathSegmentToMarket(segment: string): Market | null {
  return legacySourceToMarket(segment);
}
