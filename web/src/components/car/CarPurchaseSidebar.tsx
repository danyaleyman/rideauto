"use client";

import Link from "next/link";
import { motion, useReducedMotion } from "framer-motion";
import { useMemo, useState } from "react";
import { Check, Copy, ExternalLink, GitCompareArrows, Heart } from "lucide-react";
import { useAuth } from "@/components/AuthProvider";
import { useFavorites } from "@/hooks/use-favorites";
import { useCompareCars } from "@/hooks/use-compare-cars";
import { useLocaleContext } from "@/components/LocaleProvider";
import { getCarPageAbsoluteUrl } from "@/lib/car-url";
import { formatPriceLabel } from "@/lib/format-price";
import { priceOnRequestLabel } from "@/lib/format-price-locale";
import { buildPriceBreakdownRows } from "@/lib/car-price-breakdown";
import { formatHumanDate } from "@/lib/car-detail-data";
import { type CarListingAvailability, carSourceDisplayName } from "@/lib/car-listing-trust";
import { Button } from "@/components/ui/button";
import { CatalogQuickBuyDialog } from "@/components/catalog/CatalogQuickBuyDialog";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { CarAdminPanel } from "@/components/car/CarAdminPanel";
import { PriceBenchmarkInsight } from "@/components/catalog/PriceBenchmarkInsight";
import { useCarPriceBenchmarkQuery } from "@/hooks/use-car-price-benchmark";
import { MOTION_PRESETS, MOTION_TOKENS } from "@/components/ui/motion";
import type { SlimCar } from "@/lib/types";

type Props = {
  carId: string;
  title: string;
  priceRub: number | null;
  priceOnRequest?: boolean;
  availability?: CarListingAvailability;
  sourceUrl: string | null;
  priceWon: number | null;
  priceCny: number | null;
  sourceLabel: string | null;
  catalogCreatedAt?: string | null;
  sourceUpdatedAt?: string | null;
  calcDetails?: Record<string, unknown> | null;
  carData?: Record<string, unknown>;
  photoUrls?: string[];
};

function slimForFavorite(id: string, title: string, price: number | null): SlimCar {
  return { id, title, price, data: {} };
}

export function CarPurchaseSidebar({
  carId,
  title,
  priceRub,
  priceOnRequest = false,
  availability = "available",
  sourceUrl,
  priceWon,
  priceCny,
  sourceLabel,
  catalogCreatedAt,
  sourceUpdatedAt,
  calcDetails,
  carData,
  photoUrls = [],
}: Props) {
  const reduceMotion = useReducedMotion();
  const { t, locale } = useLocaleContext();
  const { authenticated } = useAuth();
  const { toggle, isFavorite } = useFavorites();
  const { toggle: toggleCompare, isInCompare, full: compareFull } = useCompareCars();
  const fav = authenticated && isFavorite(carId);
  const inCompare = isInCompare(carId);
  const [copied, setCopied] = useState(false);

  const listingUnavailable = availability === "sold" || availability === "reserved";

  const priceBenchmarkQuery = useCarPriceBenchmarkQuery(
    carId,
    !priceOnRequest && priceRub != null && !listingUnavailable,
  );

  const breakdownRows = useMemo(
    () =>
      buildPriceBreakdownRows({
        priceRub,
        priceOnRequest,
        priceWon,
        priceCny,
        carId,
        calcDetails,
        listingUnavailable,
      }),
    [priceRub, priceOnRequest, priceWon, priceCny, carId, calcDetails, listingUnavailable],
  );

  const updatedLabel = formatHumanDate(sourceUpdatedAt);
  const createdLabel = formatHumanDate(catalogCreatedAt);

  return (
    <motion.aside
      id="car-order-panel"
      className="relative max-w-full overflow-hidden rounded-xl border border-border bg-card p-5 sm:p-6 lg:sticky lg:top-[calc(var(--site-header-height,3.5rem)+1.5rem)]"
      initial={reduceMotion ? false : { opacity: 0, y: MOTION_TOKENS.offsets.fadeUpSm }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-80px" }}
      transition={reduceMotion ? { duration: 0.01 } : { duration: 0.3, ease: MOTION_TOKENS.easeSoft }}
    >
      <h2 className="sr-only">{t("car.purchase.panelSr")}</h2>
      <p className="text-sm text-muted-foreground">
        {listingUnavailable ? t("car.purchase.statusHeading") : t("car.purchase.priceHeading")}
      </p>
      <p className="mt-1 break-words text-3xl font-semibold leading-tight tracking-tight text-foreground [overflow-wrap:anywhere] tabular-nums">
        {availability === "sold"
          ? t("car.purchase.sold")
          : availability === "reserved"
            ? t("car.purchase.reserved")
            : priceOnRequest
              ? priceOnRequestLabel(locale)
              : priceRub != null && !Number.isNaN(priceRub)
                ? formatPriceLabel(priceRub)
                : priceOnRequestLabel(locale)}
      </p>
      <p className="mt-2 line-clamp-2 text-sm font-medium leading-snug text-foreground">
        {title}
      </p>
      {(updatedLabel || createdLabel || sourceLabel) ? (
        <p className="mt-2 text-xs leading-relaxed text-muted-foreground">
          {[
            sourceLabel ? t("car.purchase.source", { name: carSourceDisplayName(sourceLabel) }) : null,
            updatedLabel ? t("car.purchase.updated", { date: updatedLabel }) : null,
            createdLabel ? t("car.purchase.catalogAdded", { date: createdLabel }) : null,
          ]
            .filter(Boolean)
            .join(" · ")}
        </p>
      ) : null}

      <PriceBenchmarkInsight
        variant="car"
        data={priceBenchmarkQuery.data}
        loading={priceBenchmarkQuery.isFetching && !priceBenchmarkQuery.data}
      />

      {/* До lg те же CTA живут в CarStickyMobileBar — не дублируем их в карточке цены. */}
      <div className="mt-5 hidden flex-col gap-2 lg:flex">
        {availability === "available" ? (
          <CatalogQuickBuyDialog
            carId={carId}
            carTitle={title}
            triggerLabel={t("car.purchase.buyCta")}
            triggerSize="lg"
            triggerVariant="default"
            triggerClassName="w-full text-title-sm font-semibold"
          />
        ) : null}
        <motion.div {...(reduceMotion ? {} : MOTION_PRESETS.pressable)}>
          <Button variant="outline" size="lg" className="w-full text-title-sm font-medium" asChild>
            <Link href="/contacts">{t("car.purchase.contactManager")}</Link>
          </Button>
        </motion.div>
      </div>

      <div className="mt-3 flex min-w-0 flex-wrap items-center gap-1 lg:mt-4">
        {sourceUrl ? (
          <Button variant="ghost" size="icon-sm" className="rounded-md text-muted-foreground hover:text-foreground" asChild>
            <a
              href={sourceUrl}
              target="_blank"
              rel="noopener noreferrer"
              title={t("car.purchase.originalListing")}
              aria-label={t("car.purchase.openOriginal")}
            >
              <ExternalLink className="size-4" aria-hidden />
            </a>
          </Button>
        ) : null}
        <Button
          type="button"
          variant="ghost"
          size="icon-sm"
          className="rounded-md text-muted-foreground hover:text-foreground"
          title={copied ? t("car.purchase.linkCopied") : t("car.purchase.copyLink")}
          aria-label={copied ? t("car.purchase.linkCopied") : t("car.purchase.copyListingLink")}
          onClick={() => {
            void navigator.clipboard.writeText(getCarPageAbsoluteUrl(carId)).then(() => {
              setCopied(true);
              window.setTimeout(() => setCopied(false), 2000);
            });
          }}
        >
          {copied ? (
            <Check className="size-4 text-green-600" aria-hidden />
          ) : (
            <Copy className="size-4" aria-hidden />
          )}
        </Button>
        <Button
          type="button"
          variant={inCompare ? "secondary" : "ghost"}
          size="icon-sm"
          className={inCompare ? "rounded-md" : "rounded-md text-muted-foreground hover:text-foreground"}
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
          onClick={() => toggleCompare(carId)}
        >
          <GitCompareArrows className="size-4" aria-hidden />
        </Button>
        {authenticated ? (
          <Button
            type="button"
            variant="ghost"
            size="icon-sm"
            className={fav ? "rounded-md text-red-600 hover:text-red-700" : "rounded-md text-muted-foreground hover:text-foreground"}
            title={fav ? t("car.purchase.inFavorites") : t("car.purchase.addFavorite")}
            aria-label={fav ? t("car.purchase.removeFavorite") : t("car.purchase.addFavoriteAria")}
            aria-pressed={fav}
            onClick={() => {
              void toggle(slimForFavorite(carId, title, priceRub));
            }}
          >
            <Heart className={fav ? "size-4 fill-current" : "size-4"} aria-hidden />
          </Button>
        ) : null}

        <Dialog>
          <DialogTrigger asChild>
            <Button
              variant="link"
              size="sm"
              className="ms-auto h-8 px-2 text-xs font-medium text-muted-foreground hover:text-foreground"
            >
              {t("car.purchase.priceBreakdown")}
            </Button>
          </DialogTrigger>
          <DialogContent
            className="flex max-h-[min(92vh,44rem)] flex-col gap-4 overflow-hidden sm:max-h-none sm:max-w-lg sm:overflow-visible"
            showCloseButton
          >
            <DialogHeader className="shrink-0">
              <DialogTitle>{t("car.purchase.breakdownTitle")}</DialogTitle>
              <DialogDescription>{t("car.purchase.breakdownDesc")}</DialogDescription>
            </DialogHeader>
            <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain [-ms-overflow-style:none] [scrollbar-width:none] sm:overflow-visible sm:[scrollbar-width:auto]">
              {breakdownRows.length === 0 ? (
                <p className="text-sm text-muted-foreground">{t("car.purchase.breakdownEmpty")}</p>
              ) : (
                <ul className="divide-y divide-border text-sm">
                  {breakdownRows.map((row) => (
                    <li key={row.label} className="flex flex-col gap-0.5 py-2.5">
                      <div className="flex items-baseline justify-between gap-3">
                        <span className="text-muted-foreground">{row.label}</span>
                        <span className="font-semibold tabular-nums text-foreground">{row.value}</span>
                      </div>
                      {row.note ? <span className="text-xs text-muted-foreground">{row.note}</span> : null}
                      {row.subRows && row.subRows.length > 0 ? (
                        <ul className="mt-1 space-y-1.5 ps-3">
                          {row.subRows.map((sub) => (
                            <li
                              key={`${row.label}-${sub.label}`}
                              className="flex items-center justify-between gap-3 text-xs"
                            >
                              <span className="text-muted-foreground">{sub.label}</span>
                              <span className="font-medium tabular-nums text-foreground">{sub.value}</span>
                            </li>
                          ))}
                        </ul>
                      ) : null}
                    </li>
                  ))}
                </ul>
              )}
            </div>
            <p className="shrink-0 text-xs text-muted-foreground">
              {t("car.purchase.breakdownFootnote")}
            </p>
          </DialogContent>
        </Dialog>
      </div>

      {carData ? (
        <div className="mt-4">
          <CarAdminPanel
            carId={carId}
            title={title}
            data={carData}
            photoUrls={photoUrls}
            priceRub={priceRub}
            priceOnRequest={priceOnRequest}
            publishedAt={sourceUpdatedAt ?? catalogCreatedAt ?? null}
          />
        </div>
      ) : null}
    </motion.aside>
  );
}
