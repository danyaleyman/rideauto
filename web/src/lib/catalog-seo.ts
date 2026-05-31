import type { CatalogUrlState } from "@/lib/catalog-url";
import { createT, type AppLocale } from "@/lib/i18n";

export type CatalogSeo = {
  title: string;
  description: string;
  /** false → robots noindex,follow (шумные комбинации фильтров не индексируем). */
  index: boolean;
};

function fmtRub(raw: string, locale: AppLocale): string | null {
  const n = Number(raw.replace(/\s/g, ""));
  if (!Number.isFinite(n) || n <= 0) return null;
  return new Intl.NumberFormat(locale === "en" ? "en-US" : "ru-RU").format(Math.round(n));
}

function subjectPhrase(state: CatalogUrlState, locale: AppLocale): string {
  const t = createT(locale);
  const mark = state.marks.length === 1 ? state.marks[0] : "";
  const model = mark && state.models.length === 1 ? state.models[0] : "";
  if (mark && model) return `${mark} ${model}`;
  if (mark) return mark;
  return t("catalog.seo.vehicles");
}

/** Есть ли «шумные» фильтры/состояние, при которых страницу не стоит индексировать. */
export function catalogIsIndexable(state: CatalogUrlState): boolean {
  if (state.q) return false;
  if (state.page > 1) return false;
  if (state.sort && state.sort !== "date_new") return false;
  if (state.marks.length > 1 || state.models.length > 1) return false;
  if (
    state.clusters.length ||
    state.generations.length ||
    state.trims.length ||
    state.body.length ||
    state.fuel.length ||
    state.trans.length ||
    state.color.length
  ) {
    return false;
  }
  if (
    state.price_from ||
    state.price_to ||
    state.mileage_from ||
    state.mileage_to ||
    state.year_from ||
    state.year_to ||
    state.engine_cc_from ||
    state.engine_cc_to
  ) {
    return false;
  }
  if (
    state.passable_only ||
    state.pricing_tier ||
    state.customs_included_only ||
    state.power_hp_le_160 ||
    state.drive_awd ||
    state.no_accidents_only ||
    state.new_only
  ) {
    return false;
  }
  if (state.models.length === 1 && state.marks.length !== 1) return false;
  return true;
}

/** Заголовок/описание каталога из активных фасетов (марка/модель/цена/год/регион). */
export function buildCatalogSeo(state: CatalogUrlState, locale: AppLocale = "ru"): CatalogSeo {
  const t = createT(locale);
  const market =
    state.market === "china" ? t("catalog.seo.marketChina") : t("catalog.seo.marketKorea");
  const index = catalogIsIndexable(state);

  if (state.q) {
    return {
      title: t("catalog.seo.searchTitle", { q: state.q }),
      description: t("catalog.seo.searchDesc", { q: state.q, market }),
      index: false,
    };
  }

  const subject = subjectPhrase(state, locale);
  const titleParts: string[] = [`${subject} ${market}`];

  const priceTo = state.price_to ? fmtRub(state.price_to, locale) : null;
  const priceFrom = state.price_from ? fmtRub(state.price_from, locale) : null;
  if (priceTo) titleParts.push(t("catalog.seo.priceUpTo", { price: priceTo }));
  else if (priceFrom) titleParts.push(t("catalog.seo.priceFrom", { price: priceFrom }));

  if (state.year_from && state.year_to) {
    titleParts.push(t("catalog.seo.yearRange", { from: state.year_from, to: state.year_to }));
  } else if (state.year_from) {
    titleParts.push(t("catalog.seo.yearFrom", { year: state.year_from }));
  } else if (state.year_to) {
    titleParts.push(t("catalog.seo.yearTo", { year: state.year_to }));
  }

  const title = titleParts.join(" ").trim();
  const subjectLower =
    subject === t("catalog.seo.vehicles") ? t("catalog.seo.vehiclesLower") : subject;
  const description = t("catalog.seo.description", { subject: subjectLower, market });

  return { title, description, index };
}
