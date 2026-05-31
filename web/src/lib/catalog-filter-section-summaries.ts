import type { CatalogUrlState } from "@/lib/catalog-url";
import { createT, type AppLocale } from "@/lib/i18n";

function joinParts(parts: string[], max = 3): string {
  const slice = parts.filter(Boolean).slice(0, max);
  if (!slice.length) return "";
  if (parts.length > max) return `${slice.join(" · ")} +${parts.length - max}`;
  return slice.join(" · ");
}

function rangeSummary(
  locale: AppLocale,
  from: string,
  to: string,
  unit: string,
): string | null {
  const f = from.trim();
  const t = to.trim();
  if (!f && !t) return null;
  if (f && t) return `${f}–${t} ${unit}`;
  if (f) return `≥ ${f} ${unit}`;
  return `≤ ${t} ${unit}`;
}

export function vehicleFilterSummary(state: CatalogUrlState, locale: AppLocale): string {
  const parts: string[] = [];
  if (state.marks.length) parts.push(...state.marks);
  if (state.models.length) parts.push(...state.models);
  if (state.generations.length) parts.push(...state.generations.slice(0, 1));
  if (!parts.length && state.q.trim()) return state.q.trim();
  return joinParts(parts, 2);
}

export function conditionFilterSummary(state: CatalogUrlState, locale: AppLocale): string {
  const t = createT(locale);
  const flags: string[] = [];
  if (state.drive_awd) flags.push(t("catalog.filters.awdShort"));
  if (state.power_hp_le_160) flags.push(t("catalog.filters.hp160Short"));
  if (state.no_accidents_only) flags.push(t("catalog.filters.noAccidentsShort"));
  if (state.new_only) flags.push(t("catalog.filters.newOnlyShort"));
  if (state.passable_only) flags.push(t("catalog.filters.passableShort"));
  return joinParts(flags, 4);
}

export function techFilterSummary(
  state: CatalogUrlState,
  locale: AppLocale,
  facetLabels: Map<string, string>,
): string {
  const parts: string[] = [];
  for (const v of [...state.body, ...state.fuel, ...state.trans].slice(0, 4)) {
    parts.push(facetLabels.get(v) ?? v);
  }
  return joinParts(parts, 3);
}

export function rangesFilterSummary(state: CatalogUrlState, locale: AppLocale): string {
  const t = createT(locale);
  const parts: string[] = [];
  const price = rangeSummary(locale, state.price_from, state.price_to, "₽");
  if (price) parts.push(price);
  const year = rangeSummary(locale, state.year_from, state.year_to, "");
  if (year) parts.push(year.replace(/\s+$/, " г."));
  const km = rangeSummary(locale, state.mileage_from, state.mileage_to, t("catalog.filters.kmUnit"));
  if (km) parts.push(km);
  if (state.pricing_tier === "full_customs") parts.push(t("catalog.filters.tierFullShort"));
  else if (state.pricing_tier === "korea_land_only") parts.push(t("catalog.filters.tierLandShort"));
  else if (state.pricing_tier === "price_on_request") parts.push(t("catalog.filters.tierPorShort"));
  return joinParts(parts, 3);
}

export function colorFilterSummary(
  state: CatalogUrlState,
  facetLabels: Map<string, string>,
): string {
  const parts = state.color.map((v) => facetLabels.get(v) ?? v);
  return joinParts(parts, 3);
}
