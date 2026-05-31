"use client";

import { useCallback, useEffect, useState } from "react";
import { motion, useMotionValue, type PanInfo } from "framer-motion";
import { SlidersHorizontal, X } from "lucide-react";
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
        "sticky z-20 -mx-3 mb-1 flex min-w-0 items-center gap-2 border-b border-border/50 bg-background/90 px-3 py-2.5 backdrop-blur-md",
        "top-[calc(var(--site-header-height,3.5rem)+env(safe-area-inset-top,0px))]",
        "lg:hidden",
      )}
    >
      <Button
        type="button"
        variant="outline"
        className="min-h-11 flex-1 justify-start gap-2 rounded-2xl px-3.5 font-normal"
        aria-expanded={open}
        onClick={() => setOpen(true)}
      >
        <SlidersHorizontal className="size-4 shrink-0 opacity-70" aria-hidden />
        <span className="truncate">
          {t("catalog.filters.mobileTitle")}
          {activeCount > 0 ? (
            <span className="ms-1.5 tabular-nums text-muted-foreground">({activeCount})</span>
          ) : null}
        </span>
      </Button>
      {activeCount > 0 ? (
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className="min-h-11 shrink-0 rounded-2xl px-3 text-xs"
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
            "flex h-[min(92dvh,var(--sheet-max-h,92vh))] max-h-[inherit] flex-col gap-0 overflow-hidden rounded-t-3xl border-0 p-0 shadow-xl",
            "fixed inset-x-0 bottom-0 top-auto max-w-none",
            "!translate-x-0 !translate-y-0 start-0",
            "data-[state=open]:slide-in-from-bottom data-[state=closed]:slide-out-to-bottom",
            "sm:max-w-lg sm:rounded-3xl sm:inset-x-auto sm:bottom-auto sm:start-1/2 sm:top-1/2 sm:!-translate-x-1/2 sm:!-translate-y-1/2",
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
                variant="secondary"
                className="min-h-11 w-full rounded-2xl font-semibold"
                onClick={() => setOpen(false)}
              >
                {t("catalog.filters.mobileApplyCount", {
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
