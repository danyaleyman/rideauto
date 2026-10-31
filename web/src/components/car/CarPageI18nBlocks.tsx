"use client";

import Link from "next/link";
import { useState } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";
import { useLocaleContext } from "@/components/LocaleProvider";
import { ProxiedListingImage } from "@/components/car/ProxiedListingImage";
import { TranslateButton } from "@/components/car/TranslateButton";
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
import { MotionStagger, MotionStaggerItem } from "@/components/ui/motion";
import { BuyCalculatorLazy } from "@/components/buy/BuyCalculatorLazy";
import { catalogCardAttributeChips } from "@/lib/catalog-client-utils";
import { getAllCarPhotoUrls } from "@/lib/car-gallery-images";
import { formatCatalogCardPriceLocale } from "@/lib/format-price-locale";
import { lotBuyCalculatorPreset } from "@/lib/lot-buy-calculator-preset";
import type { CarListingAvailability } from "@/lib/car-listing-trust";
import type { SlimCar } from "@/lib/types";

const DESCRIPTION_LONG_THRESHOLD = 280;


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
          variant="link"
          size="sm"
          className="h-auto shrink-0 px-0 text-xs text-muted-foreground hover:text-foreground sm:text-sm"
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
        className="mb-4 rounded-lg border border-red-600/30 bg-red-600/10 px-4 py-3 text-sm text-red-900 dark:text-red-100"
        role="status"
      >
        {t("car.detail.soldBanner")}
      </div>
    );
  }
  if (availability === "reserved") {
    return (
      <div
        className="mb-4 rounded-lg border border-amber-600/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-950 dark:text-amber-50"
        role="status"
      >
        {t("car.detail.reservedBanner")}
      </div>
    );
  }
  return null;
}

/**
 * Секция «Описание» — аккордеон-заголовок, коллапс длинного текста,
 * кнопка «Перевести» через DeepSeek.
 */
export function CarDescriptionSection({ description }: { description: string }) {
  const { t } = useLocaleContext();
  const isLong = description.length > DESCRIPTION_LONG_THRESHOLD;
  const [expanded, setExpanded] = useState(!isLong);
  const [translated, setTranslated] = useState<string | null>(null);
  const displayText = translated ?? description;

  return (
    <section
      id="car-description"
      className="scroll-mt-20 border-t border-border pt-5 sm:scroll-mt-24 lg:scroll-mt-32"
    >
      {/* Заголовок-аккордеон + кнопка перевода */}
      <div className="flex min-w-0 items-center justify-between gap-3">
        <button
          type="button"
          className="group flex min-w-0 flex-1 items-center gap-2 text-start"
          aria-expanded={expanded}
          onClick={() => setExpanded((v) => !v)}
        >
          <h2 className="font-heading text-base font-semibold tracking-tight">
            {t("car.detail.description")}
          </h2>
          {expanded ? (
            <ChevronUp className="size-4 shrink-0 text-muted-foreground transition-transform group-hover:text-foreground" aria-hidden />
          ) : (
            <ChevronDown className="size-4 shrink-0 text-muted-foreground transition-transform group-hover:text-foreground" aria-hidden />
          )}
        </button>
        <TranslateButton
          text={description}
          isTranslated={translated !== null}
          onTranslated={setTranslated}
          onRevert={() => setTranslated(null)}
        />
      </div>

      {/* Текст с коллапсом */}
      {expanded ? (
        <p className="mt-3 whitespace-pre-wrap text-[15px] leading-relaxed text-foreground/85 [overflow-wrap:anywhere]">
          {displayText}
        </p>
      ) : (
        <div className="relative mt-3">
          <p
            className="whitespace-pre-wrap text-[15px] leading-relaxed text-foreground/85 [overflow-wrap:anywhere]"
            style={{
              display: "-webkit-box",
              WebkitLineClamp: 4,
              WebkitBoxOrient: "vertical",
              overflow: "hidden",
            }}
          >
            {displayText}
          </p>
          <div className="pointer-events-none absolute bottom-0 left-0 right-0 h-8 bg-gradient-to-t from-background to-transparent" />
        </div>
      )}

      {/* Кнопка раскрыть/свернуть — только если текст длинный */}
      {isLong ? (
        <button
          type="button"
          className="mt-2 flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
          onClick={() => setExpanded((v) => !v)}
        >
          {expanded ? (
            <>
              <ChevronUp className="size-3.5" aria-hidden />
              {t("car.detail.descriptionCollapse")}
            </>
          ) : (
            <>
              <ChevronDown className="size-3.5" aria-hidden />
              {t("car.detail.descriptionExpand")}
            </>
          )}
        </button>
      ) : null}
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
      <MotionStagger className="mt-5 grid min-w-0 grid-cols-1 items-stretch gap-4 sm:mt-6 sm:grid-cols-2 sm:gap-5 lg:grid-cols-3 xl:grid-cols-4">
        {similar.map((car) => {
          const cardData = (car.data ?? {}) as Record<string, unknown>;
          const img = getAllCarPhotoUrls(cardData)[0];
          const simSold = Boolean(car.encar_listing_sold || car.che168_listing_sold);
          const simReserved = !simSold && Boolean(car.encar_listing_reserved);
          const attrChips = catalogCardAttributeChips(cardData, car.year_num, locale);
          return (
            <MotionStaggerItem key={car.id} className="h-full min-w-0">
              <Link
                href={`/car/${encodeURIComponent(car.id)}`}
                className="group flex h-full min-w-0 flex-col overflow-hidden rounded-xl border border-border bg-card transition-[border-color,box-shadow] hover:border-foreground/20 hover:shadow-[0_6px_24px_-12px_rgba(15,23,42,0.25)]"
              >
                <div className="relative aspect-[4/3] shrink-0 overflow-hidden bg-muted">
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
                <div className="flex min-w-0 flex-1 flex-col p-3 sm:p-3.5">
                  <p className="line-clamp-2 min-h-[2.5rem] break-words text-sm font-semibold leading-snug [overflow-wrap:anywhere] group-hover:text-primary">
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
                  <p className="mt-auto pt-2 break-words text-base font-semibold tabular-nums text-foreground [overflow-wrap:anywhere]">
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

export function CarLotCalculatorSection({ data }: { data: Record<string, unknown> }) {
  const { t } = useLocaleContext();
  const preset = lotBuyCalculatorPreset(data);
  return (
    <section
      id="car-lot-calc"
      className="relative mx-auto mt-12 min-w-0 max-w-[1440px] scroll-mt-20 border-t border-border px-3 pt-8 sm:scroll-mt-24 sm:px-6 sm:pt-10 lg:scroll-mt-32 lg:px-10"
    >
      <h2 className="font-heading text-lg font-semibold tracking-tight sm:text-xl md:text-2xl">
        {t("car.detail.lotCalcTitle")}
      </h2>
      <p className="mt-1 text-sm text-muted-foreground">{t("car.detail.lotCalcHint")}</p>
      <div className="mt-5 sm:mt-6">
        <BuyCalculatorLazy preset={preset} />
      </div>
    </section>
  );
}
