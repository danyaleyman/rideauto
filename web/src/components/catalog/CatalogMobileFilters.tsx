"use client";

import { useCallback, useEffect, useState } from "react";
import { motion, useMotionValue, type PanInfo } from "framer-motion";
import { SlidersHorizontal, X } from "lucide-react";
import { SortDropdown } from "@/components/catalog/CatalogBlockWidgets";
import { CatalogFiltersContent } from "@/components/catalog/CatalogFiltersContent";
import type { CatalogSearchController } from "@/hooks/use-catalog-search-state";
import { useBodyScrollLock } from "@/hooks/use-body-scroll-lock";
import { useVisualViewportHeight } from "@/hooks/use-visual-viewport-height";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useLocaleContext } from "@/components/LocaleProvider";
import { cn } from "@/lib/utils";

const DRAG_CLOSE_OFFSET_PX = 72;
const DRAG_CLOSE_VELOCITY = 480;

/** Мобильная / планшетная панель фильтров (< lg). */
export function CatalogMobileFilters({ catalog }: { catalog: CatalogSearchController }) {
  const { t, locale } = useLocaleContext();
  const [open, setOpen] = useState(false);
  const activeCount = catalog.activeChips.length;
  const total = catalog.search.meta?.total ?? 0;
  const { state, rangeDraft, loading, applyRanges } = catalog;
  const hasPendingRanges =
    rangeDraft.price_from !== state.price_from ||
    rangeDraft.price_to !== state.price_to ||
    rangeDraft.mileage_from !== state.mileage_from ||
    rangeDraft.mileage_to !== state.mileage_to ||
    rangeDraft.year_from !== state.year_from ||
    rangeDraft.year_to !== state.year_to ||
    rangeDraft.engine_cc_from !== state.engine_cc_from ||
    rangeDraft.engine_cc_to !== state.engine_cc_to ||
    rangeDraft.passable_only !== state.passable_only;
  const viewportH = useVisualViewportHeight();
  const dragY = useMotionValue(0);

  useBodyScrollLock(open);

  useEffect(() => {
    if (!open) dragY.set(0);
  }, [open, dragY]);

  const sheetMaxHeight = Math.min(viewportH * 0.92, viewportH - 16);

  const handleDragEnd = useCallback(
    (_event: MouseEvent | TouchEvent | PointerEvent, info: PanInfo) => {
      if (info.offset.y > DRAG_CLOSE_OFFSET_PX || info.velocity.y > DRAG_CLOSE_VELOCITY) {
        setOpen(false);
      } else {
        dragY.set(0);
      }
    },
    [dragY],
  );

  return (
    <div
      className={cn(
        "sticky z-20 -mx-3 mb-3 flex min-w-0 items-center gap-2 border-b border-border bg-background/95 px-3 py-2 backdrop-blur-md sm:-mx-6 sm:px-6",
        "top-[calc(var(--site-header-height,3.5rem)+env(safe-area-inset-top,0px))]",
        "lg:hidden",
      )}
    >
      <Button
        type="button"
        variant="outline"
        className="h-10 min-w-0 flex-1 justify-start gap-2 px-3 font-medium"
        data-testid="catalog-mobile-filters-open"
        aria-expanded={open}
        onClick={() => setOpen(true)}
      >
        <SlidersHorizontal className="size-4 shrink-0" aria-hidden />
        <span className="truncate">
          {t("catalog.filters.mobileTitle")}
          {activeCount > 0 ? (
            <span className="ms-1.5 tabular-nums text-muted-foreground">({activeCount})</span>
          ) : null}
        </span>
      </Button>
      <SortDropdown
        variant="toolbar"
        value={catalog.state.sort}
        onChange={(sort) => catalog.navigate({ ...catalog.state, sort, page: 1 })}
      />
      {activeCount > 0 ? (
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className="h-10 shrink-0 px-2.5 text-xs text-muted-foreground"
          data-testid="catalog-mobile-filters-reset"
          onClick={() => catalog.reset()}
        >
          {t("catalog.filters.mobileReset")}
        </Button>
      ) : null}

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent
          showCloseButton={false}
          overlayClassName="touch-none sm:touch-auto"
          onOpenAutoFocus={(e) => e.preventDefault()}
          onPointerDownOutside={(e) => {
            const target = e.target as HTMLElement;
            if (target.closest("[data-slot=dropdown-menu-content]")) {
              e.preventDefault();
            }
          }}
          className={cn(
            "flex h-[min(92dvh,var(--sheet-max-h,92vh))] max-h-[inherit] flex-col gap-0 overflow-hidden rounded-t-2xl border-0 p-0 shadow-xl",
            "fixed inset-x-0 bottom-0 top-auto max-w-none",
            "!translate-x-0 !translate-y-0 start-0",
            "data-[state=open]:slide-in-from-bottom data-[state=closed]:slide-out-to-bottom",
            "sm:max-w-lg sm:rounded-2xl sm:inset-x-auto sm:bottom-auto sm:start-1/2 sm:top-1/2 sm:!-translate-x-1/2 sm:!-translate-y-1/2",
          )}
          style={{ maxHeight: sheetMaxHeight, ["--sheet-max-h" as string]: `${sheetMaxHeight}px` }}
        >
          <div className="flex min-h-0 flex-1 flex-col">
            <motion.div
              className="flex shrink-0 cursor-grab flex-col items-center border-b border-border/60 px-4 pt-2 active:cursor-grabbing"
              style={{ y: dragY }}
              drag="y"
              dragConstraints={{ top: 0, bottom: 0 }}
              dragElastic={{ top: 0, bottom: 0.35 }}
              onDragEnd={handleDragEnd}
            >
              <div
                className="mb-2 h-1 w-10 shrink-0 rounded-full bg-muted-foreground/35"
                aria-hidden
              />
              <DialogHeader className="w-full space-y-0 pb-3.5 text-start">
                <div className="flex items-center justify-between gap-2">
                  <DialogTitle className="text-base font-semibold">
                    {t("catalog.filters.mobileTitle")}
                    {activeCount > 0 ? (
                      <span className="ms-1.5 font-normal text-muted-foreground">
                        ({activeCount})
                      </span>
                    ) : null}
                  </DialogTitle>
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon-sm"
                    className="shrink-0 rounded-full"
                    aria-label={t("catalog.filters.mobileClose")}
                    onClick={() => setOpen(false)}
                  >
                    <X className="size-4" aria-hidden />
                  </Button>
                </div>
              </DialogHeader>
            </motion.div>
            <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain touch-pan-y [-webkit-overflow-scrolling:touch]">
              <div className="px-4 py-4">
                <CatalogFiltersContent catalog={catalog} inBottomSheet />
              </div>
            </div>
            <DialogFooter className="shrink-0 border-t border-border/60 px-4 py-3 pb-[max(0.75rem,env(safe-area-inset-bottom))]">
              <Button
                type="button"
                className="min-h-11 w-full font-semibold"
                data-testid="catalog-mobile-filters-apply"
                onClick={() => {
                  applyRanges();
                  setOpen(false);
                }}
              >
                {loading || hasPendingRanges
                  ? t("catalog.filters.mobileApply")
                  : t("catalog.filters.mobileApplyCount", {
                      count: total.toLocaleString(locale === "en" ? "en-US" : "ru-RU"),
                    })}
              </Button>
            </DialogFooter>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
