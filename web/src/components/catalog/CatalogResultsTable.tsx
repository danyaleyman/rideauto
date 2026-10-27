"use client";

import Link from "next/link";
import dynamic from "next/dynamic";
import type { MouseEvent } from "react";
import { catalogCardMetaParts, previewImageUrls, shouldShowPendingNavigation } from "@/lib/catalog-client-utils";
import { buildCatalogCardDisplayData } from "@/lib/catalog-listing-card";
import { formatCatalogCardPrice } from "@/lib/format-price";
import type { CatalogSearchController } from "@/hooks/use-catalog-search-state";
import type { SlimCar } from "@/lib/types";
import { CatalogCardImage } from "@/components/catalog/CatalogBlockWidgets";
import { useLocaleContext } from "@/components/LocaleProvider";
import { useCompareCars } from "@/hooks/use-compare-cars";
import { touchIconButtonClass } from "@/lib/design-system";
import { Button } from "@/components/ui/button";
import { GitCompareArrows, Heart } from "lucide-react";
import { cn } from "@/lib/utils";

const CatalogQuickBuyDialog = dynamic(
  () => import("@/components/catalog/CatalogQuickBuyDialog").then((m) => m.CatalogQuickBuyDialog),
  { ssr: false },
);

export function CatalogResultsTable({
  catalog,
  cars,
}: {
  catalog: CatalogSearchController;
  cars: SlimCar[];
}) {
  const { t, locale } = useLocaleContext();
  const { state, openingCarId, setOpeningCarId, proxiedCatalogThumbsByCar, catalogGridThumbRows } = catalog;
  const { authenticated, isFavorite, toggleFavorite } = catalog;
  const { toggle: toggleCompare, isInCompare, full: compareFull } = useCompareCars();

  const markOpening = (carId: string) => (e: MouseEvent<HTMLAnchorElement>) => {
    if (shouldShowPendingNavigation(e)) setOpeningCarId(carId);
  };

  return (
    <div className="mt-1 overflow-x-auto">
      <table className="w-full min-w-[44rem] border-t border-border text-start text-sm">
        <caption className="sr-only">{t("catalog.results.listLabel")}</caption>
        <thead>
          <tr className="border-b border-border text-xs text-muted-foreground">
            <th scope="col" className="w-20 py-2.5 pe-3 font-medium">
              {t("catalog.results.tablePhoto")}
            </th>
            <th scope="col" className="py-2.5 pe-3 font-medium">
              {t("catalog.results.tableCar")}
            </th>
            <th scope="col" className="w-28 py-2.5 pe-3 font-medium">
              {t("catalog.results.tableYear")}
            </th>
            <th scope="col" className="w-32 py-2.5 pe-3 font-medium">
              {t("catalog.results.tableMileage")}
            </th>
            <th scope="col" className="w-40 py-2.5 pe-3 font-medium">
              {t("catalog.results.tablePrice")}
            </th>
            <th scope="col" className="w-44 py-2.5 font-medium">
              <span className="sr-only">{t("catalog.quickBuy.trigger")}</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {cars.map((car, idx) => {
            const { cardData, normalizedTitle } = buildCatalogCardDisplayData(car);
            const meta = catalogCardMetaParts(cardData, car.year_num, locale);
            const year = meta[0] ?? "—";
            const mileage = meta[1] ?? "—";
            const listingSold = Boolean(car.encar_listing_sold || car.che168_listing_sold);
            const listingReserved = !listingSold && Boolean(car.encar_listing_reserved);
            const listingUnavailable = listingSold || listingReserved;
            const preview =
              proxiedCatalogThumbsByCar.get(car.id)?.urls ??
              catalogGridThumbRows[idx]?.urls ??
              previewImageUrls(car);
            const opening = openingCarId === car.id;
            const href = `/car/${encodeURIComponent(car.id)}`;
            const inCompare = isInCompare(car.id);
            const fav = authenticated && isFavorite(car.id);

            return (
              <tr
                key={car.id}
                className={cn(
                  "border-b border-border last:border-b-0",
                  opening && "bg-muted/40",
                )}
              >
                <td className="py-2.5 pe-3 align-middle">
                  <Link
                    href={href}
                    prefetch
                    onClick={markOpening(car.id)}
                    className="relative block aspect-[16/10] w-[4.5rem] overflow-hidden bg-muted"
                    aria-label={t("catalog.card.openListing", { title: normalizedTitle })}
                  >
                    <CatalogCardImage
                      images={preview}
                      displayImages={preview}
                      lqipSrc={proxiedCatalogThumbsByCar.get(car.id)?.lqip}
                      alt=""
                      eager={idx < 8}
                    />
                  </Link>
                </td>
                <td className="py-2.5 pe-3 align-middle">
                  <Link
                    href={href}
                    prefetch
                    onClick={markOpening(car.id)}
                    className="font-medium leading-snug text-foreground underline-offset-4 hover:underline"
                  >
                    {normalizedTitle}
                  </Link>
                  <p className="mt-0.5 text-xs text-muted-foreground">
                    {t(
                      state.market === "china"
                        ? "catalog.market.china"
                        : state.market === "usa"
                          ? "catalog.market.usa"
                          : "catalog.market.korea",
                    )}
                  </p>
                </td>
                <td className="py-2.5 pe-3 align-middle tabular-nums text-muted-foreground">{year}</td>
                <td className="py-2.5 pe-3 align-middle tabular-nums text-muted-foreground">{mileage}</td>
                <td className="py-2.5 pe-3 align-middle font-semibold tabular-nums">
                  {listingUnavailable
                    ? listingReserved
                      ? t("catalog.card.reserved")
                      : t("catalog.card.sold")
                    : formatCatalogCardPrice(car.price, car.price_on_request)}
                </td>
                <td className="py-2.5 align-middle">
                  <div className="flex items-center justify-end gap-1">
                    {listingUnavailable ? null : (
                      <CatalogQuickBuyDialog
                        carId={car.id}
                        carTitle={normalizedTitle}
                        triggerClassName="h-8 px-3 text-xs font-semibold"
                      />
                    )}
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
                      aria-label={inCompare ? t("car.purchase.compareRemove") : t("car.purchase.compareAdd")}
                      disabled={!inCompare && compareFull}
                      onClick={() => toggleCompare(car.id)}
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
                        onClick={() => void toggleFavorite(car)}
                      >
                        <Heart className={cn("size-4", fav ? "fill-current" : "")} aria-hidden />
                      </Button>
                    ) : (
                      <Button
                        variant="ghost"
                        size="icon-sm"
                        asChild
                        className={cn(touchIconButtonClass, "rounded-md text-muted-foreground hover:text-foreground")}
                        title={t("favorites.loginRequired")}
                      >
                        <Link href="/login" aria-label={t("favorites.loginRequired")}>
                          <Heart className="size-4" aria-hidden />
                        </Link>
                      </Button>
                    )}
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
