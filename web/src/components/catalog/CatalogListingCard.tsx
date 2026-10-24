"use client";

import Link from "next/link";
import dynamic from "next/dynamic";
import { motion } from "framer-motion";
import type { MouseEvent } from "react";
import {
  catalogCardMetaParts,
  catalogCardPrimaryCommerce,
  shouldShowPendingNavigation,
} from "@/lib/catalog-client-utils";
import { buildCatalogCardDisplayData } from "@/lib/catalog-listing-card";
import { getCarPageAbsoluteUrl } from "@/lib/car-url";
import { isCatalogListedToday } from "@/lib/catalog-listed-today";
import { formatCatalogCardPrice } from "@/lib/format-price";
import type { CatalogSearchController } from "@/hooks/use-catalog-search-state";
import type { SlimCar } from "@/lib/types";
import { cardItemVariants, CatalogCardImage } from "@/components/catalog/CatalogBlockWidgets";
import { catalogListingThumbFocusClass, listingCardSurfaceClass, touchIconButtonClass } from "@/lib/design-system";
import { useCompareCars } from "@/hooks/use-compare-cars";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { ListingChip } from "@/components/ui/listing-chip";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { Check, CircleHelp, Copy, GitCompareArrows, Heart, Loader2 } from "lucide-react";
import { useLocaleContext } from "@/components/LocaleProvider";

const CatalogQuickBuyDialog = dynamic(
  () => import("@/components/catalog/CatalogQuickBuyDialog").then((m) => m.CatalogQuickBuyDialog),
  {
    ssr: false,
    loading: () => (
      <span
        className="ms-auto inline-flex h-7 min-w-[4.5rem] shrink-0 animate-pulse rounded-lg bg-muted/60"
        aria-hidden
      />
    ),
  },
);

export type CatalogListingCardProps = {
  catalog: CatalogSearchController;
  car: SlimCar;
  idx: number;
  preview: string[];
};

function marketLabelKey(market: string): string {
  if (market === "china") return "catalog.market.china";
  if (market === "usa") return "catalog.market.usa";
  return "catalog.market.korea";
}

export function CatalogListingCard({ catalog, car, idx, preview }: CatalogListingCardProps) {
  const { t, locale } = useLocaleContext();
  const {
    reduceMotion,
    state,
    copiedId,
    setCopiedId,
    openingCarId,
    setOpeningCarId,
    authenticated,
    isFavorite,
    toggleFavorite,
    proxiedCatalogThumbsByCar,
    catalogDensity,
  } = catalog;
  const compact = catalogDensity === "compact";
  const { toggle: toggleCompare, isInCompare, full: compareFull } = useCompareCars();
  const inCompare = isInCompare(car.id);

  const { cardData, normalizedTitle } = buildCatalogCardDisplayData(car);
  const listedToday = isCatalogListedToday(car.catalog_created_at);
  const metaParts = catalogCardMetaParts(cardData, car.year_num, locale);
  const primaryCommerce = catalogCardPrimaryCommerce(cardData, car.year_num, car.pricing_tier);
  const listingSold = Boolean(car.encar_listing_sold || car.che168_listing_sold);
  const listingReserved = !listingSold && Boolean(car.encar_listing_reserved);
  const listingUnavailable = listingSold || listingReserved;
  const fav = authenticated && isFavorite(car.id);
  const showCopied = copiedId === car.id;
  const openingThisCard = openingCarId === car.id;

  const commerceBadge =
    !listingUnavailable && primaryCommerce ? (
      primaryCommerce.kind === "no_customs" ? (
        <ListingChip tone="commerceAmber" size={compact ? "sm" : "md"}>
          {t("catalog.card.noCustoms")}
          <Tooltip>
            <TooltipTrigger asChild>
              <button
                type="button"
                className="inline-flex shrink-0"
                aria-label={t("catalog.card.noCustomsAria")}
              >
                <CircleHelp className="size-3.5" />
              </button>
            </TooltipTrigger>
            <TooltipContent side="top" className="max-w-[20rem]">
              {t("catalog.card.noCustomsTip")}
            </TooltipContent>
          </Tooltip>
        </ListingChip>
      ) : primaryCommerce.kind === "passable" ? (
        <ListingChip tone="commerceEmerald" size={compact ? "sm" : "md"}>
          {t("catalog.card.passable")}
          <Tooltip>
            <TooltipTrigger asChild>
              <button
                type="button"
                className="inline-flex shrink-0"
                aria-label={t("catalog.card.passableAria")}
              >
                <CircleHelp className="size-3.5" />
              </button>
            </TooltipTrigger>
            <TooltipContent side="top">{t("catalog.card.passableTip")}</TooltipContent>
          </Tooltip>
        </ListingChip>
      ) : (
        <ListingChip tone="commerceAmber" size={compact ? "sm" : "md"}>
          {t("catalog.card.highRate")}
          <Tooltip>
            <TooltipTrigger asChild>
              <button
                type="button"
                className="inline-flex shrink-0"
                aria-label={
                  primaryCommerce.passability === "young"
                    ? t("catalog.card.youngAria")
                    : t("catalog.card.oldAria")
                }
              >
                <CircleHelp className="size-3.5" />
              </button>
            </TooltipTrigger>
            <TooltipContent side="top">
              {primaryCommerce.passability === "young"
                ? t("catalog.card.youngTip")
                : t("catalog.card.oldTip")}
            </TooltipContent>
          </Tooltip>
        </ListingChip>
      )
    ) : null;

  const buyTriggerClass = "relative z-[2] shrink-0 text-xs font-semibold";
  const carHref = `/car/${encodeURIComponent(car.id)}`;
  const markOpening = (e: MouseEvent<HTMLAnchorElement>) => {
    if (shouldShowPendingNavigation(e)) setOpeningCarId(car.id);
  };

  return (
    <motion.li key={car.id} variants={reduceMotion ? undefined : cardItemVariants} layout>
      <Card
        data-slot="listing-card"
        data-density={catalogDensity}
        size="sm"
        className={cn(
          "relative flex flex-col items-stretch gap-0 overflow-clip !py-0 data-[size=sm]:!py-0 md:flex-row",
          listingCardSurfaceClass,
        )}
      >
        {/* Primary hit-area: whole card opens listing; actions sit above with z-[2]. */}
        <Link
          href={carHref}
          prefetch
          className="absolute inset-0 z-[1] rounded-[inherit] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
          aria-label={t("catalog.card.openListing", { title: normalizedTitle })}
          onClick={markOpening}
        />
        {openingThisCard ? (
          <div className="pointer-events-none absolute inset-0 z-20 flex items-center justify-center bg-background/65 backdrop-blur-[1px]">
            <span className="inline-flex items-center gap-2 rounded-full border border-border bg-background px-3 py-1.5 text-xs font-medium text-foreground">
              <Loader2 className="size-3.5 animate-spin" aria-hidden />
              {t("catalog.card.loading")}
            </span>
          </div>
        ) : null}
        <div className={cn(catalogListingThumbFocusClass, "pointer-events-none relative z-0")}>
          <div className="relative size-full">
            <CatalogCardImage
              images={preview}
              displayImages={proxiedCatalogThumbsByCar.get(car.id)?.urls ?? preview}
              lqipSrc={proxiedCatalogThumbsByCar.get(car.id)?.lqip}
              alt={normalizedTitle}
              eager={idx < 4}
            />
            {listedToday ? (
              <div className="pointer-events-none absolute inset-x-0 top-0 flex items-start bg-gradient-to-b from-black/55 via-black/25 to-transparent px-2 pb-6 pt-2">
                <ListingChip tone="overlayDark" size="sm" className="py-0.5">
                  {t("catalog.card.listedToday")}
                </ListingChip>
              </div>
            ) : null}
            {listingReserved ? (
              <div className="pointer-events-none absolute inset-x-0 bottom-0 flex items-end bg-gradient-to-t from-black/50 via-black/20 to-transparent px-2 pb-2 pt-10">
                <ListingChip tone="overlayStatusReserved" size="sm">
                  {t("catalog.card.reserved")}
                </ListingChip>
              </div>
            ) : null}
          </div>
        </div>
        <div
          className={cn(
            "relative z-0 flex min-w-0 flex-1 flex-col gap-1.5 p-3.5 sm:p-4 md:p-5",
            compact && "gap-1 p-3 sm:p-3.5 md:p-4",
          )}
        >
          <div className="flex items-start justify-between gap-2 sm:gap-3">
            <p className="font-heading pointer-events-none line-clamp-2 min-w-0 flex-1 text-base font-semibold leading-snug sm:text-[1.0625rem]">
              {normalizedTitle}
            </p>
            <div className="relative z-[2] -me-1 -mt-1 flex shrink-0 items-start gap-0.5">
              <Button
                type="button"
                variant="ghost"
                size="icon-sm"
                className={cn(touchIconButtonClass, "rounded-md text-muted-foreground hover:text-foreground")}
                title={showCopied ? t("catalog.card.copied") : t("catalog.card.copyLink")}
                aria-label={showCopied ? t("catalog.card.linkCopied") : t("catalog.card.copyLink")}
                onClick={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  void navigator.clipboard
                    .writeText(getCarPageAbsoluteUrl(car.id))
                    .then(() => {
                      setCopiedId(car.id);
                      window.setTimeout(
                        () => setCopiedId((c) => (c === car.id ? null : c)),
                        1800,
                      );
                    })
                    .catch(() => {});
                }}
              >
                {showCopied ? (
                  <Check className="size-4 text-green-600 dark:text-green-400" aria-hidden />
                ) : (
                  <Copy className="size-4" aria-hidden />
                )}
              </Button>
              <Button
                type="button"
                variant={inCompare ? "secondary" : "ghost"}
                size="icon-sm"
                className={cn(
                  touchIconButtonClass,
                  "rounded-md",
                  inCompare ? "text-foreground" : "text-muted-foreground hover:text-foreground",
                )}
                title={
                  inCompare
                    ? t("car.purchase.compareRemove")
                    : compareFull
                      ? t("car.purchase.compareFull")
                      : t("car.purchase.compareAdd")
                }
                aria-pressed={inCompare}
                aria-label={
                  inCompare ? t("car.purchase.compareRemove") : t("car.purchase.compareAdd")
                }
                disabled={!inCompare && compareFull}
                onClick={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  toggleCompare(car.id);
                }}
              >
                <GitCompareArrows className="size-4" aria-hidden />
              </Button>
              {authenticated ? (
                <Button
                  type="button"
                  variant="ghost"
                  size="icon-sm"
                  className={cn(
                    touchIconButtonClass,
                    "rounded-md",
                    fav ? "text-red-600 hover:text-red-700" : "text-muted-foreground hover:text-foreground",
                  )}
                  title={fav ? t("car.purchase.removeFavorite") : t("car.purchase.addFavorite")}
                  aria-pressed={fav}
                  aria-label={fav ? t("car.purchase.removeFavorite") : t("car.purchase.addFavoriteAria")}
                  onClick={(e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    void toggleFavorite(car);
                  }}
                >
                  <Heart className={cn("size-4", fav ? "fill-current" : "")} aria-hidden />
                </Button>
              ) : null}
            </div>
          </div>
          <p
            className="pointer-events-none min-w-0 text-[13px] leading-relaxed text-muted-foreground"
            aria-label={t("catalog.card.attrList")}
          >
            <span>{t(marketLabelKey(state.market))}</span>
            {metaParts.map((part, i) => (
              <span key={`${car.id}-meta-${i}`}>
                <span className="mx-1.5 text-muted-foreground/50" aria-hidden>
                  ·
                </span>
                {part}
              </span>
            ))}
          </p>
          {!listingUnavailable ? (
            <div className={cn("mt-auto flex w-full min-w-0 flex-wrap items-center justify-between gap-2 pt-3", compact && "pt-2")}>
              <div className="pointer-events-none flex min-w-0 flex-1 flex-wrap items-center gap-2">
                <span className="block max-w-full truncate text-lg font-semibold tabular-nums tracking-tight [overflow-wrap:anywhere] max-md:min-w-[5rem] sm:text-xl">
                  {formatCatalogCardPrice(car.price, car.price_on_request)}
                </span>
                {commerceBadge ? (
                  <div className="pointer-events-auto relative z-[2] flex min-w-0 flex-wrap items-center gap-1.5">
                    {commerceBadge}
                  </div>
                ) : null}
              </div>
              <CatalogQuickBuyDialog
                carId={car.id}
                carTitle={normalizedTitle}
                triggerClassName={cn(buyTriggerClass, "ms-auto h-9 px-4")}
              />
            </div>
          ) : null}
        </div>
      </Card>
    </motion.li>
  );
}
