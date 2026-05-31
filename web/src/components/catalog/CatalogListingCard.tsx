"use client";

import Link from "next/link";
import dynamic from "next/dynamic";
import { motion } from "framer-motion";
import {
  cardOverlayBadges,
  carPassabilityStatus,
  catalogCardAttributeChips,
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
  const attrChips = catalogCardAttributeChips(cardData, car.year_num, locale);
  const passability = carPassabilityStatus(cardData, car.year_num);
  const overlayBadges = cardOverlayBadges(cardData, car.year_num, state.market);
  const listingSold = Boolean(car.encar_listing_sold || car.che168_listing_sold);
  const listingReserved = !listingSold && Boolean(car.encar_listing_reserved);
  const listingUnavailable = listingSold || listingReserved;
  const fav = authenticated && isFavorite(car.id);
  const showCopied = copiedId === car.id;
  const openingThisCard = openingCarId === car.id;
  const commerceStatusBadges =
    !listingUnavailable ? (
      <>
        {car.pricing_tier === "korea_land_only" ? (
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
        ) : null}
        {passability === "passable" ? (
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
        ) : passability === "young" ? (
          <ListingChip tone="commerceAmber" size={compact ? "sm" : "md"}>
            {t("catalog.card.highRate")}
            <Tooltip>
              <TooltipTrigger asChild>
                <button
                  type="button"
                  className="inline-flex shrink-0"
                  aria-label={t("catalog.card.youngAria")}
                >
                  <CircleHelp className="size-3.5" />
                </button>
              </TooltipTrigger>
              <TooltipContent side="top">{t("catalog.card.youngTip")}</TooltipContent>
            </Tooltip>
          </ListingChip>
        ) : passability === "old" ? (
          <ListingChip tone="commerceAmber" size={compact ? "sm" : "md"}>
            {t("catalog.card.highRate")}
            <Tooltip>
              <TooltipTrigger asChild>
                <button
                  type="button"
                  className="inline-flex shrink-0"
                  aria-label={t("catalog.card.oldAria")}
                >
                  <CircleHelp className="size-3.5" />
                </button>
              </TooltipTrigger>
              <TooltipContent side="top">{t("catalog.card.oldTip")}</TooltipContent>
            </Tooltip>
          </ListingChip>
        ) : null}
      </>
    ) : null;
  const buyTriggerClass =
    "shrink-0 rounded-full border-primary/25 bg-primary text-xs font-semibold text-primary-foreground shadow-sm hover:bg-primary/92";

  return (
    <motion.li key={car.id} variants={reduceMotion ? undefined : cardItemVariants} layout>
      <Card
        data-slot="listing-card"
        data-density={catalogDensity}
        size="sm"
        className={cn(
          "relative flex flex-col items-stretch gap-0 overflow-clip !py-0 data-[size=sm]:!py-0 md:flex-row",
          listingCardSurfaceClass,
          "!shadow-sm hover:!shadow-md",
        )}
      >
        {openingThisCard ? (
          <div className="pointer-events-none absolute inset-0 z-20 flex items-center justify-center bg-background/65 backdrop-blur-[1px]">
            <span className="inline-flex items-center gap-2 rounded-full border border-border/70 bg-background/95 px-3 py-1.5 text-xs font-medium text-foreground shadow-sm">
              <Loader2 className="size-3.5 animate-spin" aria-hidden />
              {t("catalog.card.loading")}
            </span>
          </div>
        ) : null}
        <Link
          href={`/car/${encodeURIComponent(car.id)}`}
          prefetch
          className={catalogListingThumbFocusClass}
          onClick={(e) => {
            if (shouldShowPendingNavigation(e)) setOpeningCarId(car.id);
          }}
        >
          <div className="relative size-full">
            <CatalogCardImage
              images={preview}
              displayImages={proxiedCatalogThumbsByCar.get(car.id)?.urls ?? preview}
              lqipSrc={proxiedCatalogThumbsByCar.get(car.id)?.lqip}
              alt={normalizedTitle}
              eager={idx < 4}
              sold={listingUnavailable}
            />
            {listedToday ? (
              <div className="pointer-events-none absolute inset-x-0 top-0 flex items-start bg-gradient-to-b from-black/55 via-black/25 to-transparent px-2 pb-6 pt-2">
                <ListingChip tone="overlayDark" size="sm" className="py-0.5">
                  {t("catalog.card.listedToday")}
                </ListingChip>
              </div>
            ) : null}
            <div className="pointer-events-none absolute inset-x-0 bottom-0 flex items-end justify-between gap-2 bg-gradient-to-t from-black/50 via-black/20 to-transparent px-2 pb-2 pt-14">
              <div className="flex flex-wrap items-center gap-1">
                {overlayBadges.length ? (
                  overlayBadges.map((b, i) => (
                    <ListingChip
                      key={`${car.id}-ob-${i}`}
                      tone="overlay"
                      size="sm"
                      className="max-w-[10rem] truncate sm:max-w-[12rem]"
                      title={b}
                    >
                      {b}
                    </ListingChip>
                  ))
                ) : (
                  <ListingChip tone="overlay" size="sm">
                    {car.year_num ? `${car.year_num}` : "—"}
                  </ListingChip>
                )}
                {listingSold ? (
                  <ListingChip tone="overlayStatusSold" size="sm">
                    {t("catalog.card.sold")}
                  </ListingChip>
                ) : listingReserved ? (
                  <ListingChip tone="overlayStatusReserved" size="sm">
                    {t("catalog.card.reserved")}
                  </ListingChip>
                ) : null}
              </div>
            </div>
          </div>
        </Link>
        <div className="flex min-w-0 flex-1 flex-col justify-between gap-0 md:rounded-e-2xl">
          <div
            className={cn(
              "flex items-start justify-between gap-2 border-b border-border/50 px-3 py-2.5 sm:gap-3 sm:px-4 sm:py-3.5 md:px-5",
              compact && "px-2.5 py-2 sm:px-3 sm:py-2.5",
            )}
          >
            <Link
              href={`/car/${encodeURIComponent(car.id)}`}
              prefetch
              className="flex min-w-0 flex-1 items-start focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              onClick={(e) => {
                if (shouldShowPendingNavigation(e)) setOpeningCarId(car.id);
              }}
            >
              <p className="font-heading line-clamp-2 text-title-sm font-semibold sm:text-base">
                {normalizedTitle}
              </p>
            </Link>
            <div className="flex shrink-0 items-start gap-1.5 pt-px">
              <Button
                type="button"
                variant="secondary"
                size="icon-sm"
                className={cn(touchIconButtonClass, "rounded-lg shadow-sm")}
                title={showCopied ? t("catalog.card.copied") : t("catalog.card.copyLink")}
                aria-label={showCopied ? t("catalog.card.linkCopied") : t("catalog.card.copyLink")}
                onClick={() => {
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
                variant={inCompare ? "default" : "secondary"}
                size="icon-sm"
                className={cn(touchIconButtonClass, "rounded-lg shadow-sm")}
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
                onClick={() => toggleCompare(car.id)}
              >
                <GitCompareArrows className="size-4" aria-hidden />
              </Button>
              {authenticated ? (
                <Button
                  type="button"
                  variant={fav ? "default" : "secondary"}
                  size="icon-sm"
                  className={cn(touchIconButtonClass, "rounded-lg shadow-sm")}
                  title={fav ? t("car.purchase.removeFavorite") : t("car.purchase.addFavorite")}
                  aria-pressed={fav}
                  aria-label={fav ? t("car.purchase.removeFavorite") : t("car.purchase.addFavoriteAria")}
                  onClick={() => {
                    void toggleFavorite(car);
                  }}
                >
                  <Heart className={cn("size-4", fav ? "fill-current" : "")} aria-hidden />
                </Button>
              ) : null}
            </div>
          </div>
          <div
            className={cn(
              "flex items-start px-3 pb-1.5 pt-1.5 sm:px-4 sm:pb-2 sm:pt-2.5 md:px-5 md:pt-3 lg:justify-start",
              compact && "px-2.5 py-1 sm:px-3",
            )}
          >
            {attrChips.length ? (
              <Link
                href={`/car/${encodeURIComponent(car.id)}`}
                prefetch
                className="min-w-0 flex-1 rounded-lg outline-none focus-visible:ring-2 focus-visible:ring-ring lg:max-w-xl"
                onClick={(e) => {
                  if (shouldShowPendingNavigation(e)) setOpeningCarId(car.id);
                }}
                aria-label={t("catalog.card.openListing", { title: normalizedTitle })}
              >
                <ul
                  className="flex min-w-0 flex-wrap justify-start gap-1.5 md:gap-2"
                  aria-label={t("catalog.card.attrList")}
                >
                  {attrChips.map((c) => {
                    const Icon = c.Icon;
                    return (
                      <li key={c.key} className="min-w-0 max-w-full">
                        <ListingChip tone="neutral" size={compact ? "sm" : "md"} className="normal-case">
                          <Icon className="size-3 shrink-0 opacity-80" aria-hidden />
                          <span className="min-w-0">{c.label}</span>
                        </ListingChip>
                      </li>
                    );
                  })}
                </ul>
              </Link>
            ) : null}
          </div>
          <div
            className={cn(
              "border-t border-border/50 px-3 py-2.5 sm:px-4 md:px-5 max-sm:bg-muted/30 max-sm:dark:bg-muted/20",
              compact && "px-2.5 py-2 sm:px-3",
            )}
          >
            {!listingUnavailable ? (
              <div className="flex w-full min-w-0 flex-wrap items-center justify-between gap-2">
                <div className="flex min-w-0 flex-1 flex-wrap items-center gap-2">
                  <Link
                    href={`/car/${encodeURIComponent(car.id)}`}
                    prefetch
                    className="inline-flex max-w-full rounded-lg outline-none focus-visible:ring-2 focus-visible:ring-ring"
                    onClick={(e) => {
                      if (shouldShowPendingNavigation(e)) setOpeningCarId(car.id);
                    }}
                    aria-label={t("catalog.card.openPrice", { title: normalizedTitle })}
                  >
                    <span className="text-price block max-w-full truncate [overflow-wrap:anywhere] max-md:min-w-[5rem]">
                      {formatCatalogCardPrice(car.price, car.price_on_request)}
                    </span>
                  </Link>
                  <div className="flex min-w-0 flex-wrap items-center gap-1.5">{commerceStatusBadges}</div>
                </div>
                <CatalogQuickBuyDialog
                  carId={car.id}
                  carTitle={normalizedTitle}
                  triggerClassName={cn(buyTriggerClass, "ms-auto min-h-10")}
                />
              </div>
            ) : null}
          </div>
        </div>
      </Card>
    </motion.li>
  );
}
