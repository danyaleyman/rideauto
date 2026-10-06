"use client";

import { Search, X } from "lucide-react";
import { SortDropdown } from "@/components/catalog/CatalogBlockWidgets";
import { CatalogDensityToggle } from "@/components/catalog/CatalogDensityToggle";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import type { CatalogSearchController } from "@/hooks/use-catalog-search-state";
import { useLocaleContext } from "@/components/LocaleProvider";
import { cn } from "@/lib/utils";

/** Панель над выдачей: поиск, сортировка, плотность списка. */
export function CatalogResultsToolbar({ catalog }: { catalog: CatalogSearchController }) {
  const { t } = useLocaleContext();
  const {
    state,
    qDraft,
    setQDraft,
    navigate,
    loading,
    search,
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
        "mb-4 flex min-w-0 flex-col gap-3 rounded-2xl border border-border/60 bg-muted/20 p-3 shadow-sm",
        "sm:flex-row sm:flex-wrap sm:items-center sm:gap-2.5 lg:sticky lg:top-[calc(var(--site-header-height,3.5rem)+0.5rem)] lg:z-10 lg:backdrop-blur-md",
      )}
      role="search"
      aria-label={t("catalog.toolbar.aria")}
    >
      <div className="relative min-w-0 flex-1 basis-[min(100%,20rem)]">
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
          className={cn(
            "h-10 min-w-0 border-border/80 bg-background ps-9 shadow-sm",
            hasQuery ? "pe-28" : "pe-20",
          )}
          aria-label={t("catalog.filters.searchLabel")}
        />
        {hasQuery ? (
          <Button
            type="button"
            size="icon-sm"
            variant="ghost"
            className="absolute end-[4.25rem] top-1/2 h-8 w-8 -translate-y-1/2 rounded-lg text-muted-foreground hover:text-foreground"
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
          className="absolute end-1 top-1/2 h-8 -translate-y-1/2 rounded-lg px-3 text-xs"
          onClick={applySearch}
        >
          {t("catalog.filters.searchSubmit")}
        </Button>
      </div>
      <div className="flex min-w-0 flex-wrap items-center gap-2 sm:ms-auto">
        <SortDropdown
          variant="toolbar"
          value={state.sort}
          onChange={(sort) => navigate({ ...state, sort, page: 1 })}
        />
        <CatalogDensityToggle value={catalogDensity} onChange={setCatalogDensity} />
        {loading ? (
          <span className="text-xs tabular-nums text-muted-foreground">{t("catalog.results.updating")}</span>
        ) : (
          <span className="hidden text-xs tabular-nums text-muted-foreground xl:inline">
            {search.meta.total.toLocaleString("ru-RU")}
          </span>
        )}
      </div>
    </div>
  );
}
