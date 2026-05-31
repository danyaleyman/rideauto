"use client";

import { CarListingAttributeChips } from "@/components/car/CarListingAttributeChips";
import { CarListingCommerceBadges } from "@/components/car/CarListingCommerceBadges";
import { useLocaleContext } from "@/components/LocaleProvider";
import { type CarListingAvailability, carSourceDisplayName } from "@/lib/car-listing-trust";
import { parseListingCalendarYear } from "@/lib/catalog-client-utils";

/** Заголовок и ключевые факты под галереей (чипы — те же, что в каталоге). */
export function CarHeroMeta({
  title,
  data,
  sourceLabel,
  availability = "available",
  yearNum,
}: {
  title: string;
  data: Record<string, unknown>;
  sourceLabel?: string | null;
  availability?: CarListingAvailability;
  yearNum?: number | null;
}) {
  const { t } = useLocaleContext();
  const resolvedYear =
    yearNum ??
    parseListingCalendarYear(data.year) ??
    parseListingCalendarYear(data.modelyear) ??
    parseListingCalendarYear(data.year_name);

  const srcHuman = sourceLabel ? carSourceDisplayName(sourceLabel) : null;
  const listingUnavailable = availability === "sold" || availability === "reserved";

  return (
    <header className="mt-6 min-w-0 border-b border-border/60 pb-8 sm:mt-8">
      {srcHuman ? (
        <p className="mb-2 break-words text-xs font-medium text-muted-foreground [overflow-wrap:anywhere]">
          {t("car.purchase.source", { name: srcHuman })}
        </p>
      ) : null}
      {availability === "sold" ? (
        <p className="mb-2 inline-flex rounded-full border border-red-900/35 bg-red-950/20 px-3 py-1 text-xs font-semibold text-red-800 dark:text-red-200">
          {t("car.detail.soldSoon")}
        </p>
      ) : availability === "reserved" ? (
        <p className="mb-2 inline-flex rounded-full border border-amber-700/40 bg-amber-500/15 px-3 py-1 text-xs font-semibold text-amber-950 dark:text-amber-100">
          {t("car.detail.reservedPlatform")}
        </p>
      ) : null}
      <h1 className="font-heading text-display-sm [overflow-wrap:anywhere] sm:text-3xl">{title}</h1>
      {!listingUnavailable ? (
        <div className="mt-3">
          <CarListingCommerceBadges data={data} yearNum={resolvedYear} />
        </div>
      ) : null}
      <CarListingAttributeChips data={data} yearNum={resolvedYear} animated className="mt-4" />
    </header>
  );
}
