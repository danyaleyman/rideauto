import { facetRowLabel } from "@/lib/catalog-client-utils";
import type { CatalogUrlState } from "@/lib/catalog-url";
import {
  normalizeCatalogDisplayLabel,
  normalizeFuelLabel,
  trimFacetLabelMinusGeneration,
} from "@/lib/car-detail-data";
import { createT, type AppLocale } from "@/lib/i18n";
import type { FacetRow } from "@/lib/types";
import { displayBodyType, displayColor, displayTransmission } from "@/lib/vehicle-spec-locale";

export type CatalogActiveChip = {
  key: keyof CatalogUrlState;
  label: string;
  value?: string;
};

export function buildCatalogActiveChips(
  state: CatalogUrlState,
  facetLabelByValue: Map<string, string>,
  locale: AppLocale = "ru",
): CatalogActiveChip[] {
  const t = createT(locale);
  const chipDisplayKey = (shown: string) =>
    (normalizeCatalogDisplayLabel(shown) ?? shown).trim().toLowerCase().replace(/\s+/g, " ");
  const withLabel = (v: string, key?: keyof CatalogUrlState) => {
    const raw = facetLabelByValue.get(v) ?? v;
    if (key === "fuel") return normalizeFuelLabel(raw) ?? raw;
    if (key === "body") return displayBodyType(locale, raw) ?? raw;
    if (key === "trans") return displayTransmission(locale, raw) ?? raw;
    if (key === "color") return displayColor(locale, raw) ?? raw;
    return normalizeCatalogDisplayLabel(raw) ?? raw;
  };
  const chips: CatalogActiveChip[] = [];
  const pushDedupByLabel = (key: keyof CatalogUrlState, prefix: string, values: string[]) => {
    const seen = new Set<string>();
    for (const raw of values) {
      const shown = withLabel(raw, key);
      const marker = chipDisplayKey(shown);
      if (seen.has(marker)) continue;
      seen.add(marker);
      chips.push({ key, label: `${prefix}: ${shown}`, value: raw });
    }
  };
  pushDedupByLabel("marks", t("catalog.chips.mark"), state.marks);
  pushDedupByLabel("clusters", t("catalog.chips.cluster"), state.clusters);
  pushDedupByLabel("models", t("catalog.chips.model"), state.models);
  pushDedupByLabel("generations", t("catalog.chips.generation"), state.generations);
  pushDedupByLabel("trims", t("catalog.chips.trim"), state.trims);
  state.body.forEach((v) =>
    chips.push({ key: "body", label: `${t("catalog.chips.body")}: ${withLabel(v, "body")}`, value: v }),
  );
  state.fuel.forEach((v) =>
    chips.push({ key: "fuel", label: `${t("catalog.chips.fuel")}: ${withLabel(v, "fuel")}`, value: v }),
  );
  state.trans.forEach((v) =>
    chips.push({
      key: "trans",
      label: `${t("catalog.chips.transmission")}: ${withLabel(v, "trans")}`,
      value: v,
    }),
  );
  state.color.forEach((v) =>
    chips.push({ key: "color", label: `${t("catalog.chips.color")}: ${withLabel(v, "color")}`, value: v }),
  );
  if (state.drive_awd) chips.push({ key: "drive_awd", label: t("catalog.chips.awd") });
  if (state.power_hp_le_160) chips.push({ key: "power_hp_le_160", label: t("catalog.chips.hp160") });
  if (state.passable_only) chips.push({ key: "passable_only", label: t("catalog.chips.passableOnly") });
  if (state.pricing_tier === "full_customs") {
    chips.push({ key: "pricing_tier", label: t("catalog.chips.tierFull") });
  } else if (state.pricing_tier === "korea_land_only") {
    chips.push({ key: "pricing_tier", label: t("catalog.chips.tierLand") });
  } else if (state.pricing_tier === "price_on_request") {
    chips.push({ key: "pricing_tier", label: t("catalog.chips.tierPor") });
  }
  if (state.customs_included_only && state.pricing_tier !== "full_customs") {
    chips.push({ key: "customs_included_only", label: t("catalog.chips.customsInPrice") });
  }
  if (state.no_accidents_only) chips.push({ key: "no_accidents_only", label: t("catalog.chips.noAccidents") });
  if (state.new_only) chips.push({ key: "new_only", label: t("catalog.chips.newOnly") });
  if (state.price_from) chips.push({ key: "price_from", label: t("catalog.chips.priceFrom", { value: state.price_from }) });
  if (state.price_to) chips.push({ key: "price_to", label: t("catalog.chips.priceTo", { value: state.price_to }) });
  if (state.mileage_from) {
    chips.push({ key: "mileage_from", label: t("catalog.chips.mileageFrom", { value: state.mileage_from }) });
  }
  if (state.mileage_to) chips.push({ key: "mileage_to", label: t("catalog.chips.mileageTo", { value: state.mileage_to }) });
  if (state.year_from) chips.push({ key: "year_from", label: t("catalog.chips.yearFrom", { value: state.year_from }) });
  if (state.year_to) chips.push({ key: "year_to", label: t("catalog.chips.yearTo", { value: state.year_to }) });
  if (state.engine_cc_from) {
    chips.push({ key: "engine_cc_from", label: t("catalog.chips.ccFrom", { value: state.engine_cc_from }) });
  }
  if (state.engine_cc_to) chips.push({ key: "engine_cc_to", label: t("catalog.chips.ccTo", { value: state.engine_cc_to }) });
  return chips;
}

export function trimFacetLabelFormatter(
  state: CatalogUrlState,
  facetLabelByValue: Map<string, string>,
): (row: FacetRow) => string {
  return (row) => {
    const base = facetRowLabel(row);
    if (state.generations.length !== 1) return base;
    const genVal = state.generations[0];
    const genLbl =
      facetLabelByValue.get(genVal) ?? normalizeCatalogDisplayLabel(genVal) ?? genVal;
    return trimFacetLabelMinusGeneration(base, genLbl);
  };
}
