import { CarListingAttributeChips } from "@/components/car/CarListingAttributeChips";
import { CarListingCommerceBadges } from "@/components/car/CarListingCommerceBadges";
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
          Источник · <span className="text-foreground">{srcHuman}</span>
        </p>
      ) : null}
      {availability === "sold" ? (
        <p className="mb-2 inline-flex rounded-full border border-red-900/35 bg-red-950/20 px-3 py-1 text-xs font-semibold text-red-800 dark:text-red-200">
          Продан — скоро уберём из каталога
        </p>
      ) : availability === "reserved" ? (
        <p className="mb-2 inline-flex rounded-full border border-amber-700/40 bg-amber-500/15 px-3 py-1 text-xs font-semibold text-amber-950 dark:text-amber-100">
          Зарезервировано на площадке
        </p>
      ) : null}
      <h1 className="font-heading text-[1.55rem] font-bold leading-snug tracking-tight text-foreground [overflow-wrap:anywhere] sm:text-3xl md:text-[2.15rem]">
        {title}
      </h1>
      {!listingUnavailable ? (
        <div className="mt-3">
          <CarListingCommerceBadges data={data} />
        </div>
      ) : null}
      <CarListingAttributeChips
        data={data}
        yearNum={resolvedYear}
        variant="detail"
        animated
        className="mt-4"
      />
    </header>
  );
}
