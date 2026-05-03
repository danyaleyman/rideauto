import type { CatalogUrlState } from "./catalog-url";
import { stateToBrowserUrl } from "./catalog-url";

/** Состояние «только рынок»: без поиска, фасетов и прочих фильтров, первая страница. */
export function defaultCatalogStateForMarket(market: CatalogUrlState["market"]): CatalogUrlState {
  return {
    market,
    q: "",
    marks: [],
    clusters: [],
    models: [],
    generations: [],
    trims: [],
    body: [],
    fuel: [],
    trans: [],
    color: [],
    price_from: "",
    price_to: "",
    mileage_from: "",
    mileage_to: "",
    year_from: "",
    year_to: "",
    engine_cc_from: "",
    engine_cc_to: "",
    passable_only: false,
    pricing_tier: "",
    customs_included_only: false,
    power_hp_le_160: false,
    drive_awd: false,
    no_accidents_only: false,
    new_only: false,
    sort: "date_new",
    page: 1,
  };
}

function stateHasDeepContext(state: CatalogUrlState): boolean {
  if (state.q.trim()) return true;
  if (state.marks.length || state.clusters.length || state.models.length) return true;
  if (state.generations.length || state.trims.length) return true;
  if (state.body.length || state.fuel.length || state.trans.length || state.color.length) return true;
  if (state.price_from || state.price_to || state.mileage_from || state.mileage_to) return true;
  if (state.year_from || state.year_to || state.engine_cc_from || state.engine_cc_to) return true;
  if (state.passable_only) return true;
  if (state.pricing_tier) return true;
  if (state.customs_included_only) return true;
  if (state.power_hp_le_160 || state.drive_awd) return true;
  if (state.no_accidents_only || state.new_only) return true;
  if (state.sort && state.sort !== "date_new") return true;
  if (state.page > 1) return true;
  return false;
}

const TRUNC = 48;

function truncateLabel(s: string, max = TRUNC): string {
  const t = s.trim();
  if (t.length <= max) return t;
  return `${t.slice(0, max - 1)}…`;
}

/**
 * Сегменты для крошек: первый с href «/», второй — «Каталог» с ссылкой на сброс фильтров при глубоком контексте,
 * последний без href — текущий контекст (или дублирует «Каталог» при простом просмотре).
 */
export function catalogBreadcrumbSegments(
  state: CatalogUrlState,
  facetLabelByValue: Map<string, string>,
): Array<{ href?: string; label: string }> {
  const base: Array<{ href?: string; label: string }> = [{ href: "/", label: "Главная" }];

  const marketOnly = defaultCatalogStateForMarket(state.market);
  const catalogBaseHref = `/catalog?${stateToBrowserUrl(marketOnly)}`;

  if (!stateHasDeepContext(state)) {
    return [...base, { label: "Каталог" }];
  }

  const parts: string[] = [];
  parts.push(state.market === "china" ? "Китай" : "Корея");

  const q = state.q.trim();
  if (q) {
    parts.push(`Поиск: ${truncateLabel(q, 36)}`);
  }

  const facetBits: string[] = [];
  for (const v of state.marks.slice(0, 2)) {
    const lb = facetLabelByValue.get(v) ?? v;
    if (lb) facetBits.push(truncateLabel(lb, 24));
  }
  if (state.models.length && facetBits.length < 2) {
    for (const v of state.models.slice(0, 1)) {
      const lb = facetLabelByValue.get(v) ?? v;
      if (lb) facetBits.push(truncateLabel(lb, 24));
    }
  }
  if (facetBits.length) {
    parts.push(facetBits.join(" · "));
  }

  const hasRangeOrFlags =
    !!(state.price_from || state.price_to || state.mileage_from || state.mileage_to) ||
    !!(state.year_from || state.year_to) ||
    state.passable_only ||
    !!state.pricing_tier ||
    state.customs_included_only ||
    state.power_hp_le_160 ||
    state.drive_awd ||
    state.no_accidents_only ||
    state.new_only ||
    state.body.length > 0 ||
    state.fuel.length > 0 ||
    state.trans.length > 0 ||
    state.color.length > 0;

  if (hasRangeOrFlags && parts.length < 3) {
    parts.push("Фильтры");
  }

  if (state.page > 1) {
    parts.push(`Стр. ${state.page}`);
  }

  const tail = truncateLabel(parts.join(" — "), 120);

  return [...base, { href: catalogBaseHref, label: "Каталог" }, { label: tail }];
}
