"use client";

import { CatalogFiltersContent } from "@/components/catalog/CatalogFiltersContent";
import { useLocaleContext } from "@/components/LocaleProvider";
import type { CatalogSearchController } from "@/hooks/use-catalog-search-state";
import { surfaceRadiusClass, elevatedRingClass } from "@/lib/design-system";
import { cn } from "@/lib/utils";

/** Desktop-only sidebar фильтров (≥ lg). */
export function CatalogFiltersAside({ catalog }: { catalog: CatalogSearchController }) {
  const { t } = useLocaleContext();
  return (
    <aside
      className="hidden w-full min-w-0 shrink-0 self-start lg:block lg:w-[23.5rem] xl:w-[24rem]"
      aria-labelledby="catalog-filters-heading"
    >
      <div
        className={cn(
          "flex max-w-full flex-col gap-3 border border-border/50 bg-card/70 p-4 shadow-sm backdrop-blur-sm sm:p-5",
          surfaceRadiusClass,
          elevatedRingClass,
        )}
      >
        <h2 id="catalog-filters-heading" className="sr-only">
          {t("catalog.filters.title")}
        </h2>
        <CatalogFiltersContent catalog={catalog} />
      </div>
    </aside>
  );
}
