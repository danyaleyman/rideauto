"use client";

import { AnimatePresence, motion } from "framer-motion";
import { Suspense, useEffect, useState } from "react";
import { carsAddedTodayLabel, previewImageUrls } from "@/lib/catalog-client-utils";
import { PER_PAGE } from "@/lib/catalog-url";
import { featureFlags } from "@/lib/feature-flags";
import type { CatalogSearchController } from "@/hooks/use-catalog-search-state";
import { CatalogListingCard } from "@/components/catalog/CatalogListingCard";
import { CatalogVirtualResultsList } from "@/components/catalog/CatalogVirtualResultsList";
import { LocaleSwitchLinks } from "@/components/LocaleSwitchLinks";
import { useLocaleContext } from "@/components/LocaleProvider";
import { cardListVariants, ListRowSkeleton } from "@/components/catalog/CatalogBlockWidgets";
import { CatalogResultsToolbar } from "@/components/catalog/CatalogResultsToolbar";
import { PriceBenchmarkInsight } from "@/components/catalog/PriceBenchmarkInsight";
import { useCatalogPriceBenchmarkQuery } from "@/hooks/use-catalog-queries";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import {
  Pagination,
  PaginationContent,
  PaginationEllipsis,
  PaginationItem,
} from "@/components/ui/pagination";
import { Skeleton } from "@/components/ui/skeleton";
import { MOTION_PRESETS, MOTION_TOKENS } from "@/components/ui/motion";
import { ChevronLeft, ChevronRight, Loader2, Sparkles } from "lucide-react";

export function CatalogResultsPanel({ catalog }: { catalog: CatalogSearchController }) {
  const { t, locale } = useLocaleContext();
  const {
    reduceMotion,
    state,
    key,
    search,
    loading,
    err,
    openingCarId,
    dailyNewCount,
    dailyNewLoading,
    resultsListRef,
    navigate,
    reset,
    removeChip,
    title,
    pageItems,
    catalogCarsDisplay,
    catalogGridThumbRows,
    proxiedCatalogThumbsByCar,
    activeChips,
    catalogDensity,
  } = catalog;

  const priceBenchmarkQuery = useCatalogPriceBenchmarkQuery(state);

  const [wideViewport, setWideViewport] = useState(false);
  useEffect(() => {
    const mq = window.matchMedia("(min-width: 1024px)");
    const sync = () => setWideViewport(mq.matches);
    sync();
    mq.addEventListener("change", sync);
    return () => mq.removeEventListener("change", sync);
  }, []);

  const useVirtualList =
    featureFlags.enableCatalogVirtualList &&
    catalogCarsDisplay.length >= featureFlags.catalogVirtualListMinItems &&
    !reduceMotion &&
    !wideViewport;
  const listPerfClass =
    featureFlags.enableCatalogVirtualList && !useVirtualList
      ? "[&>li]:content-visibility-auto [&>li]:contain-intrinsic-size-[auto_13rem]"
      : undefined;

  return (
    <div className="min-w-0 flex-1">
      <CatalogResultsToolbar catalog={catalog} />
      <section
        className="mb-5 rounded-3xl border border-border/50 bg-card/70 p-4 shadow-sm ring-1 ring-elevated-ring sm:mb-6 sm:p-5"
        aria-labelledby="catalog-results-heading"
      >
        <h1
          id="catalog-results-heading"
          className="text-base font-semibold leading-snug tracking-tight [overflow-wrap:anywhere] sm:text-lg md:text-xl"
        >
          {title}
        </h1>
        <p className="sr-only" aria-live="polite" aria-atomic="true">
          {err
            ? t("catalog.results.loadError", { message: err })
            : loading
              ? t("catalog.results.loading")
              : t("catalog.results.liveCount", {
                  total: (search.meta?.total ?? 0).toLocaleString("ru-RU"),
                  shown: catalogCarsDisplay.length,
                  page: state.page,
                })}
        </p>
        <div className="mt-3 flex min-w-0 flex-col gap-2.5">
          <div className="flex min-w-0 flex-wrap items-baseline gap-x-2 gap-y-1">
            <p className="min-w-0 text-sm leading-snug text-muted-foreground [overflow-wrap:anywhere]">
              {t("catalog.results.totalLabel")}{" "}
              <span className="font-medium text-foreground">
                {search.meta.total.toLocaleString("ru-RU")}
              </span>
              {loading ? t("catalog.results.updating") : ""}
            </p>
            <PriceBenchmarkInsight
              variant="catalog"
              data={priceBenchmarkQuery.data}
              loading={priceBenchmarkQuery.isFetching && !priceBenchmarkQuery.data}
              className="w-full min-w-0 basis-full"
            />
            {openingCarId ? (
              <span className="inline-flex items-center gap-1.5 text-xs text-muted-foreground">
                <Loader2 className="size-3.5 animate-spin" aria-hidden />
                {t("catalog.results.openingCard")}
              </span>
            ) : null}
          </div>
          <div className="flex min-w-0 flex-wrap items-center gap-2">
            {dailyNewLoading ? (
              <Skeleton className="h-10 min-w-[12rem] flex-1 rounded-full sm:max-w-xs" />
            ) : dailyNewCount !== null ? (
              <span
                className="inline-flex max-w-full min-h-10 items-center gap-1.5 rounded-full border border-white/20 bg-black/50 px-3 py-2 text-xs font-medium leading-snug text-white shadow-sm [overflow-wrap:anywhere]"
                title={t("catalog.results.dailyNewTitle")}
              >
                <Sparkles className="size-3.5 shrink-0 opacity-85 text-white" aria-hidden />
                {carsAddedTodayLabel(dailyNewCount, locale)}
              </span>
            ) : null}
            <div className="ms-auto flex min-w-0 shrink-0 items-center justify-end">
              <Suspense fallback={null}>
                <LocaleSwitchLinks className="shrink-0 text-xs text-muted-foreground" />
              </Suspense>
            </div>
          </div>
        </div>
        {activeChips.length ? (
          <motion.div
            className="mt-4 flex min-w-0 flex-wrap items-stretch gap-2"
            layout
            transition={{ duration: 0.2, ease: "easeOut" }}
          >
            <AnimatePresence initial={false}>
              {activeChips.map((chip, idx) => (
                <motion.div
                  key={`${chip.key}-${chip.value ?? idx}`}
                  layout
                  initial={MOTION_PRESETS.popInInitial}
                  animate={MOTION_PRESETS.popInAnimate}
                  exit={MOTION_PRESETS.popInExit}
                  transition={{ duration: MOTION_TOKENS.duration.fast, ease: "easeOut" }}
                >
                  <Button
                    type="button"
                    variant="secondary"
                    size="xs"
                    className="h-auto min-h-10 max-w-full justify-start whitespace-normal rounded-full px-3 py-2 text-start text-xs font-normal [overflow-wrap:anywhere]"
                    onClick={() => removeChip(chip)}
                    title={t("catalog.results.removeChip")}
                  >
                    {chip.label} ×
                  </Button>
                </motion.div>
              ))}
            </AnimatePresence>
            <Button
              type="button"
              size="xs"
              className="h-auto min-h-10 shrink-0 rounded-full px-3 py-2"
              onClick={reset}
            >
              {t("catalog.results.resetAll")}
            </Button>
          </motion.div>
        ) : null}
      </section>

      {useVirtualList ? (
        <CatalogVirtualResultsList
          key={key}
          catalog={catalog}
          cars={catalogCarsDisplay}
          className={listPerfClass}
        />
      ) : (
        <motion.ul
          ref={resultsListRef}
          aria-label={t("catalog.results.listLabel")}
          className={cn(
            "flex scroll-mt-28 flex-col gap-3 md:scroll-mt-32",
            listPerfClass,
          )}
          variants={reduceMotion ? undefined : cardListVariants}
          initial={reduceMotion ? false : "hidden"}
          animate={reduceMotion ? undefined : "show"}
          key={key}
        >
          {catalogCarsDisplay.map((car, idx) => (
            <CatalogListingCard
              key={car.id}
              catalog={catalog}
              car={car}
              idx={idx}
              preview={
                proxiedCatalogThumbsByCar.get(car.id)?.urls ??
                catalogGridThumbRows[idx]?.urls ??
                previewImageUrls(car)
              }
            />
          ))}
          {loading && search.result.length === 0
            ? Array.from({ length: PER_PAGE }).map((_, i) => <ListRowSkeleton key={`sk-${i}`} />)
            : null}
        </motion.ul>
      )}

      {catalogCarsDisplay.length < search.result.length ? (
        <p className="mt-2 text-center text-xs text-muted-foreground [overflow-wrap:anywhere]">
          {t("catalog.results.vinDedupe", {
            count: search.result.length - catalogCarsDisplay.length,
          })}
        </p>
      ) : null}

      {search.result.length === 0 && !loading && !err ? (
        <div className="mx-auto mt-16 max-w-md rounded-2xl border border-border/60 bg-card/60 px-6 py-8 text-center shadow-sm ring-1 ring-elevated-ring">
          <p className="text-base font-medium text-foreground">{t("catalog.empty.title")}</p>
          <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{t("catalog.empty.hint")}</p>
          <div className="mt-5 flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:justify-center">
            <Button type="button" className="rounded-full" variant="secondary" onClick={reset}>
              {t("catalog.empty.reset")}
            </Button>
            <Button type="button" className="rounded-full" variant="outline" asChild>
              <a href="https://t.me/nikits15" target="_blank" rel="noopener noreferrer">
                {t("catalog.empty.telegramCta")}
              </a>
            </Button>
          </div>
        </div>
      ) : null}

      <Pagination className="mt-10" aria-label={t("common.pagination")}>
        <PaginationContent className="flex-wrap justify-center gap-1">
          <PaginationItem>
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="min-h-11 gap-1 rounded-full ps-2 max-lg:px-3"
              disabled={state.page <= 1}
              aria-label={t("common.catalogPagePrev")}
              onClick={() => navigate({ ...state, page: state.page - 1 })}
            >
              <ChevronLeft className="size-4 rtl:rotate-180" aria-hidden />
              <span className="hidden sm:inline">{t("catalog.results.paginationPrev")}</span>
            </Button>
          </PaginationItem>
          {pageItems.map((item, idx) =>
            item === "ellipsis" ? (
              <PaginationItem key={`ellipsis-${idx}`}>
                <PaginationEllipsis label={t("common.pageSkipped")} />
              </PaginationItem>
            ) : (
              <PaginationItem key={item}>
                <Button
                  type="button"
                  variant={state.page === item ? "outline" : "ghost"}
                  size="sm"
                  className="min-w-9 rounded-full tabular-nums"
                  onClick={() => navigate({ ...state, page: item })}
                  aria-label={t("common.pageN", { n: item })}
                  aria-current={state.page === item ? "page" : undefined}
                >
                  {item}
                </Button>
              </PaginationItem>
            ),
          )}
          <PaginationItem>
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="min-h-11 gap-1 rounded-full pe-2 max-lg:px-3"
              disabled={!search.meta.next_cursor}
              aria-label={t("common.catalogPageNext")}
              onClick={() => navigate({ ...state, page: state.page + 1 })}
            >
              <span className="hidden sm:inline">{t("catalog.results.paginationNext")}</span>
              <ChevronRight className="size-4 rtl:rotate-180" aria-hidden />
            </Button>
          </PaginationItem>
        </PaginationContent>
      </Pagination>
    </div>
  );
}
