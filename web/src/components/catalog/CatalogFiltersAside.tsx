"use client";

import { CatalogFiltersContent } from "@/components/catalog/CatalogFiltersContent";
import { useLocaleContext } from "@/components/LocaleProvider";
import type { CatalogSearchController } from "@/hooks/use-catalog-search-state";

/** Desktop-only sidebar фильтров (≥ lg): плоская колонка без контейнера. */
export function CatalogFiltersAside({ catalog }: { catalog: CatalogSearchController }) {
  const { t } = useLocaleContext();
  return (
    <aside
      className="hidden w-full min-w-0 shrink-0 self-start lg:block lg:w-[17.5rem] xl:w-[18.5rem]"
      data-testid="catalog-filters-aside"
      aria-labelledby="catalog-filters-heading"
    >
      <h2 id="catalog-filters-heading" className="sr-only">
        {t("catalog.filters.title")}
      </h2>
      <CatalogFiltersContent catalog={catalog} />
    </aside>
  );
}
