"use client";

import { Search, X } from "lucide-react";
import { SortDropdown } from "@/components/catalog/CatalogBlockWidgets";
import { CatalogDensityToggle } from "@/components/catalog/CatalogDensityToggle";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import type { CatalogSearchController } from "@/hooks/use-catalog-search-state";
import { useLocaleContext } from "@/components/LocaleProvider";
import { cn } from "@/lib/utils";

/**
 * Панель над выдачей: поиск, сортировка, плотность списка.
 * Плоская строка без контейнера; на < lg сортировка живёт в мобильной панели фильтров.
 */
export function CatalogResultsToolbar({ catalog }: { catalog: CatalogSearchController }) {
  const { t } = useLocaleContext();
  const {
    state,
    qDraft,
    setQDraft,
    navigate,
    catalogDensity,
    setCatalogDensity,
  } = catalog;

  const applySearch = () => navigate({ ...state, q: qDraft.trim(), page: 1 });
  const clearSearch = () => {
    setQDraft("");
    if (state.q) navigate({ ...state, q: "", page: 1 });
  };
  const hasQuery = Boolean(qDraft.trim() || state.q);

  return (
    <div
      className={cn(
        "mb-4 flex min-w-0 items-center gap-2 sm:gap-3",
        "lg:sticky lg:top-[calc(var(--site-header-height,3.5rem)+0.01px)] lg:z-10 lg:-mx-2 lg:bg-background/95 lg:px-2 lg:py-2.5 lg:backdrop-blur",
      )}
      role="search"
      aria-label={t("catalog.toolbar.aria")}
    >
      <div className="relative min-w-0 flex-1">
        <Search
          className="pointer-events-none absolute start-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground"
          aria-hidden
        />
        <Input
          value={qDraft}
          onChange={(e) => setQDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") applySearch();
            if (e.key === "Escape" && hasQuery) clearSearch();
          }}
          placeholder={t("catalog.filters.searchPlaceholder")}
          className={cn("h-10 min-w-0 ps-9", hasQuery ? "pe-24" : "pe-16")}
          aria-label={t("catalog.filters.searchLabel")}
        />
        {hasQuery ? (
          <Button
            type="button"
            size="icon-sm"
            variant="ghost"
            className="absolute end-14 top-1/2 h-7 w-7 -translate-y-1/2 rounded-md text-muted-foreground hover:text-foreground"
            onClick={clearSearch}
            aria-label={t("catalog.filters.searchClear")}
            title={t("catalog.filters.searchClear")}
          >
            <X className="size-4" aria-hidden />
          </Button>
        ) : null}
        <Button
          type="button"
          size="sm"
          variant="ghost"
          className="absolute end-1 top-1/2 h-8 -translate-y-1/2 rounded-md px-2.5 text-xs font-semibold"
          onClick={applySearch}
        >
          {t("catalog.filters.searchSubmit")}
        </Button>
      </div>
      <div className="hidden shrink-0 items-center gap-2 lg:flex">
        <SortDropdown
          variant="toolbar"
          value={state.sort}
          onChange={(sort) => navigate({ ...state, sort, page: 1 })}
        />
        <CatalogDensityToggle value={catalogDensity} onChange={setCatalogDensity} />
      </div>
    </div>
  );
}
