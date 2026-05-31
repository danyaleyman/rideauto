"use client";

import Link from "next/link";
import { useLocaleContext } from "@/components/LocaleProvider";
import { ProxiedListingImage } from "@/components/car/ProxiedListingImage";
import { ListingChip } from "@/components/ui/listing-chip";
import { Button } from "@/components/ui/button";
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";
import { MotionFadeUp, MotionStagger, MotionStaggerItem } from "@/components/ui/motion";
import { catalogCardAttributeChips } from "@/lib/catalog-client-utils";
import { extractCarImageUrls } from "@/lib/car-images";
import { formatCatalogCardPriceLocale } from "@/lib/format-price-locale";
import type { CarListingAvailability } from "@/lib/car-listing-trust";
import type { SlimCar } from "@/lib/types";

export function CarPageBreadcrumbBar({ title, specsUrl }: { title: string; specsUrl?: string | null }) {
  const { t } = useLocaleContext();
  return (
    <>
      <Breadcrumb className="min-w-0 flex-1">
        <BreadcrumbList className="flex-wrap gap-x-1 gap-y-1 sm:flex-nowrap">
          <BreadcrumbItem>
            <BreadcrumbLink asChild>
              <Link href="/">{t("car.detail.home")}</Link>
            </BreadcrumbLink>
          </BreadcrumbItem>
          <BreadcrumbSeparator />
          <BreadcrumbItem>
            <BreadcrumbLink asChild>
              <Link href="/catalog">{t("car.detail.catalog")}</Link>
            </BreadcrumbLink>
          </BreadcrumbItem>
          <BreadcrumbSeparator />
          <BreadcrumbItem className="min-w-0 max-w-full">
            <BreadcrumbPage className="line-clamp-2 break-words text-start font-medium [overflow-wrap:anywhere] sm:line-clamp-1">
              {title}
            </BreadcrumbPage>
          </BreadcrumbItem>
        </BreadcrumbList>
      </Breadcrumb>
      {specsUrl ? (
        <Button
          variant="outline"
          size="sm"
          className="h-auto min-h-10 w-full shrink-0 whitespace-normal px-3 py-2 text-center text-xs shadow-sm sm:w-auto sm:text-sm"
          asChild
        >
          <a href={specsUrl} target="_blank" rel="noopener noreferrer">
            {t("car.detail.fullSpecs")}
          </a>
        </Button>
      ) : null}
    </>
  );
}

export function CarAvailabilityBanner({ availability }: { availability: CarListingAvailability }) {
  const { t } = useLocaleContext();
  if (availability === "sold") {
    return (
      <div
        className="mb-4 rounded-2xl border border-red-900/35 bg-red-950/25 px-4 py-3 text-sm text-red-50 shadow-sm backdrop-blur-sm"
        role="status"
      >
        {t("car.detail.soldBanner")}
      </div>
    );
  }
  if (availability === "reserved") {
    return (
      <div
        className="mb-4 rounded-2xl border border-amber-700/40 bg-amber-500/12 px-4 py-3 text-sm text-amber-950 shadow-sm backdrop-blur-sm dark:text-amber-50"
        role="status"
      >
        {t("car.detail.reservedBanner")}
      </div>
    );
  }
  return null;
}

export function CarDescriptionSection({ description }: { description: string }) {
  const { t } = useLocaleContext();
  return (
    <section
      id="car-description"
      className="scroll-mt-20 rounded-2xl border border-border/65 bg-card p-4 shadow-sm ring-1 ring-elevated-ring sm:scroll-mt-24 sm:rounded-3xl sm:p-6 lg:scroll-mt-32"
    >
      <h2 className="font-heading text-lg font-semibold tracking-tight">{t("car.detail.description")}</h2>
      <p className="mt-3 whitespace-pre-wrap text-sm leading-relaxed text-muted-foreground [overflow-wrap:anywhere]">
        {description}
      </p>
    </section>
  );
}

export function CarSimilarSection({ similar }: { similar: SlimCar[] }) {
  const { t, locale } = useLocaleContext();
  if (!similar.length) return null;
  return (
    <>
      <h2 className="font-heading text-lg font-semibold tracking-tight sm:text-xl md:text-2xl">
        {t("car.detail.similarTitle")}
      </h2>
      <p className="mt-1 text-sm text-muted-foreground">{t("car.detail.similarHint")}</p>
      <MotionStagger className="mt-5 grid min-w-0 grid-cols-1 gap-4 sm:mt-6 sm:grid-cols-2 sm:gap-5 lg:grid-cols-3 xl:grid-cols-4">
        {similar.map((car) => {
          const cardData = (car.data ?? {}) as Record<string, unknown>;
          const img = extractCarImageUrls(cardData)[0];
          const simSold = Boolean(car.encar_listing_sold || car.che168_listing_sold);
          const simReserved = !simSold && Boolean(car.encar_listing_reserved);
          const attrChips = catalogCardAttributeChips(cardData, car.year_num, locale);
          return (
            <MotionStaggerItem key={car.id}>
              <Link
                href={`/car/${encodeURIComponent(car.id)}`}
                className="group block min-w-0 overflow-hidden rounded-2xl border border-border/65 bg-card shadow-sm ring-1 ring-elevated-ring transition-all hover:-translate-y-px hover:border-border hover:shadow-md active:scale-[0.99]"
              >
                <div className="relative aspect-[4/3] overflow-hidden bg-muted">
                  {img ? (
                    <ProxiedListingImage
                      src={img}
                      alt={car.title || car.id}
                      width={640}
                      height={480}
                      sizes="(min-width: 1280px) 22vw, (min-width: 1024px) 28vw, (min-width: 640px) 44vw, 96vw"
                      className="size-full object-cover transition-transform duration-300 group-hover:scale-[1.03]"
                    />
                  ) : (
                    <div className="flex size-full items-center justify-center text-sm text-muted-foreground">
                      {t("car.detail.noPhoto")}
                    </div>
                  )}
                  {simSold ? (
                    <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center gap-1 bg-black/55 px-2">
                      <span className="text-center text-[11px] font-semibold leading-tight text-white sm:text-xs">
                        {t("car.purchase.sold")}
                      </span>
                      <ListingChip tone="overlayStatusSold" size="sm">
                        {t("catalog.card.sold")}
                      </ListingChip>
                    </div>
                  ) : simReserved ? (
                    <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center gap-1 bg-amber-950/50 px-2">
                      <span className="text-center text-[11px] font-semibold leading-tight text-amber-50 sm:text-xs">
                        {t("car.purchase.reserved")}
                      </span>
                      <ListingChip tone="overlayStatusReserved" size="sm">
                        {t("car.detail.reserveShort")}
                      </ListingChip>
                    </div>
                  ) : null}
                </div>
                <div className="min-w-0 p-3 sm:p-3.5">
                  <p className="line-clamp-3 break-words text-sm font-semibold leading-snug [overflow-wrap:anywhere] group-hover:text-primary sm:line-clamp-2">
                    {car.title || car.id}
                  </p>
                  {attrChips.length ? (
                    <ul className="mt-2 flex min-w-0 flex-wrap gap-1.5" aria-label={t("catalog.card.attrList")}>
                      {attrChips.slice(0, 3).map((c) => {
                        const Icon = c.Icon;
                        return (
                          <li key={c.key}>
                            <ListingChip tone="neutral" size="sm" className="normal-case">
                              <Icon className="size-3 shrink-0 opacity-80" aria-hidden />
                              <span className="min-w-0">{c.label}</span>
                            </ListingChip>
                          </li>
                        );
                      })}
                    </ul>
                  ) : null}
                  <p className="mt-2 break-words text-sm font-medium tabular-nums text-muted-foreground [overflow-wrap:anywhere]">
                    {formatCatalogCardPriceLocale(locale, car.price, car.price_on_request)}
                  </p>
                </div>
              </Link>
            </MotionStaggerItem>
          );
        })}
      </MotionStagger>
    </>
  );
}
