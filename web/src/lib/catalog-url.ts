import { decodeOffsetCursor, encodeOffsetCursor } from "./cursor";

export const PER_PAGE = 10;

export type Market = "korea" | "china";

/** Фильтр каталога по слою цены корейского каталога (Meilisearch ``pricing_tier``). Пустая строка — без фильтра. */
export type CatalogPricingTierFilter = "" | "full_customs" | "korea_land_only" | "price_on_request";

export type CatalogUrlState = {
  market: Market;
  q: string;
  marks: string[];
  clusters: string[];
  models: string[];
  generations: string[];
  trims: string[];
  body: string[];
  fuel: string[];
  trans: string[];
  color: string[];
  price_from: string;
  price_to: string;
  mileage_from: string;
  mileage_to: string;
  year_from: string;
  year_to: string;
  engine_cc_from: string;
  engine_cc_to: string;
  passable_only: boolean;
  /** Meilisearch: ``pricing_tier`` (CSV на бэкенде — в UI пока один ярус). */
  pricing_tier: CatalogPricingTierFilter;
  /** Meilisearch: ``customs_included = true`` (не путать с проходностью авто). */
  customs_included_only: boolean;
  power_hp_le_160: boolean;
  drive_awd: boolean;
  no_accidents_only: boolean;
  new_only: boolean;
  sort: string;
  page: number;
};

function parsePricingTierFilter(raw: string | null): CatalogPricingTierFilter {
  const v = (raw ?? "").trim();
  if (v === "full_customs" || v === "korea_land_only" || v === "price_on_request") {
    return v;
  }
  return "";
}

function splitCsv(v: string | null): string[] {
  if (!v) return [];
  return v
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
}

export function parseCatalogUrl(sp: URLSearchParams): CatalogUrlState {
  const region = (sp.get("region") || "").toLowerCase();
  const source = (sp.get("source") || "").toLowerCase();
  let market: Market = "korea";
  if (
    region === "china" ||
    source === "china" ||
    source === "dongchedi" ||
    source === "che168"
  ) {
    market = "china";
  }

  let page = parseInt(sp.get("page") || "1", 10);
  if (!Number.isFinite(page) || page < 1) page = 1;

  const hasExplicitPage = sp.has("page");
  const cur = (sp.get("cursor") || "").trim();
  if (cur && !hasExplicitPage) {
    const dec = decodeOffsetCursor(cur);
    if (dec && dec.limit === PER_PAGE) {
      page = Math.floor(dec.offset / PER_PAGE) + 1;
    }
  }

  return {
    market,
    q: (sp.get("q") || sp.get("query") || "").trim(),
    marks: splitCsv(sp.get("marks")),
    clusters: splitCsv(sp.get("clusters")),
    models: splitCsv(sp.get("models")),
    generations: splitCsv(sp.get("generations")),
    trims: splitCsv(sp.get("trims")),
    body: splitCsv(sp.get("body")),
    fuel: splitCsv(sp.get("fuel")),
    trans: splitCsv(sp.get("trans")),
    color: splitCsv(sp.get("color")),
    price_from: (sp.get("price_from") || "").trim(),
    price_to: (sp.get("price_to") || "").trim(),
    mileage_from: (sp.get("mileage_from") || "").trim(),
    mileage_to: (sp.get("mileage_to") || "").trim(),
    year_from: (sp.get("year_from") || "").trim(),
    year_to: (sp.get("year_to") || "").trim(),
    engine_cc_from: (sp.get("engine_cc_from") || "").trim(),
    engine_cc_to: (sp.get("engine_cc_to") || "").trim(),
    passable_only: sp.get("passable_only") === "1",
    pricing_tier: parsePricingTierFilter(sp.get("pricing_tier")),
    customs_included_only: sp.get("customs_included") === "1",
    power_hp_le_160: sp.get("power_hp_le_160") === "1",
    drive_awd: sp.get("drive_awd") === "1",
    no_accidents_only: sp.get("no_accidents_only") === "1",
    new_only: sp.get("new_only") === "1",
    sort: (sp.get("sort") || "date_new").trim() || "date_new",
    page,
  };
}

export function catalogStateFromRecord(
  raw: Record<string, string | string[] | undefined>,
): CatalogUrlState {
  const sp = new URLSearchParams();
  for (const [k, v] of Object.entries(raw)) {
    if (v === undefined) continue;
    if (Array.isArray(v)) {
      for (const x of v) sp.append(k, x);
    } else {
      sp.set(k, v);
    }
  }
  return parseCatalogUrl(sp);
}

export function catalogStateKey(state: CatalogUrlState): string {
  return stateToBrowserUrl(state);
}

function setCsv(u: URLSearchParams, key: string, values: string[]) {
  if (values.length) u.set(key, values.join(","));
  else u.delete(key);
}

export function stateToBrowserUrl(state: CatalogUrlState): string {
  const u = new URLSearchParams();
  if (state.market === "china") {
    u.set("region", "china");
    u.set("source", "dongchedi");
  } else {
    u.set("region", "korea");
    u.set("source", "encar");
  }
  if (state.q) u.set("q", state.q);
  setCsv(u, "marks", state.marks);
  setCsv(u, "clusters", state.clusters);
  setCsv(u, "models", state.models);
  setCsv(u, "generations", state.generations);
  setCsv(u, "trims", state.trims);
  setCsv(u, "body", state.body);
  setCsv(u, "fuel", state.fuel);
  setCsv(u, "trans", state.trans);
  setCsv(u, "color", state.color);
  if (state.price_from) u.set("price_from", state.price_from);
  if (state.price_to) u.set("price_to", state.price_to);
  if (state.mileage_from) u.set("mileage_from", state.mileage_from);
  if (state.mileage_to) u.set("mileage_to", state.mileage_to);
  if (state.year_from) u.set("year_from", state.year_from);
  if (state.year_to) u.set("year_to", state.year_to);
  if (state.engine_cc_from) u.set("engine_cc_from", state.engine_cc_from);
  if (state.engine_cc_to) u.set("engine_cc_to", state.engine_cc_to);
  if (state.passable_only) u.set("passable_only", "1");
  if (state.pricing_tier) u.set("pricing_tier", state.pricing_tier);
  if (state.customs_included_only) u.set("customs_included", "1");
  if (state.power_hp_le_160) u.set("power_hp_le_160", "1");
  if (state.drive_awd) u.set("drive_awd", "1");
  if (state.no_accidents_only) u.set("no_accidents_only", "1");
  if (state.new_only) u.set("new_only", "1");
  if (state.sort && state.sort !== "date_new") u.set("sort", state.sort);
  if (state.page > 1) u.set("page", String(state.page));
  const entries = [...u.entries()].sort(([a], [b]) => a.localeCompare(b));
  const sorted = new URLSearchParams();
  for (const [k, v] of entries) sorted.append(k, v);
  return sorted.toString();
}

export function toApiSearchParams(state: CatalogUrlState): URLSearchParams {
  const p = new URLSearchParams();
  p.set("per_page", String(PER_PAGE));
  if (state.market === "china") {
    p.set("region", "china");
    p.set("source", "dongchedi");
  } else {
    p.set("region", "korea");
    p.set("source", "encar");
  }
  if (state.q) p.set("q", state.q);
  setCsv(p, "marks", state.marks);
  setCsv(p, "clusters", state.clusters);
  setCsv(p, "models", state.models);
  setCsv(p, "generations", state.generations);
  setCsv(p, "trims", state.trims);
  setCsv(p, "body", state.body);
  setCsv(p, "fuel", state.fuel);
  setCsv(p, "trans", state.trans);
  setCsv(p, "color", state.color);
  if (state.price_from) p.set("price_from", state.price_from);
  if (state.price_to) p.set("price_to", state.price_to);
  if (state.mileage_from) p.set("mileage_from", state.mileage_from);
  if (state.mileage_to) p.set("mileage_to", state.mileage_to);
  if (state.year_from) p.set("year_from", state.year_from);
  if (state.year_to) p.set("year_to", state.year_to);
  if (state.engine_cc_from) p.set("engine_cc_from", state.engine_cc_from);
  if (state.engine_cc_to) p.set("engine_cc_to", state.engine_cc_to);
  if (state.passable_only) p.set("passable_only", "1");
  if (state.pricing_tier) p.set("pricing_tier", state.pricing_tier);
  if (state.customs_included_only) p.set("customs_included", "1");
  if (state.power_hp_le_160) p.set("power_hp_le_160", "1");
  if (state.drive_awd) p.set("drive_awd", "1");
  if (state.no_accidents_only) p.set("no_accidents_only", "1");
  if (state.new_only) p.set("new_only", "1");
  if (state.sort && state.sort !== "date_new") p.set("sort", state.sort);
  if (state.page > 1) {
    p.set("cursor", encodeOffsetCursor((state.page - 1) * PER_PAGE, PER_PAGE));
  }
  return p;
}

export function toFacetApiParams(state: CatalogUrlState): URLSearchParams {
  return toApiSearchParams({ ...state, page: 1 });
}

/** Плоский объект query для серверного ``fetchSearch`` (всегда с region/source по умолчанию). */
export function catalogStateToFetchParams(
  state: CatalogUrlState,
): Record<string, string> {
  const out: Record<string, string> = {};
  toApiSearchParams(state).forEach((v, k) => {
    out[k] = v;
  });
  return out;
}
