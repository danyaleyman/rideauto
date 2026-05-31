"use client";

import Image from "next/image";
import { catalogCardImagePlaceholder } from "@/lib/catalog-card-image";
import { useProxiedCatalogThumbUrls } from "@/lib/catalog-image-proxy";
import { useEffect, useMemo, useState } from "react";
import { ChevronsUpDown, CircleHelp } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { useLocaleContext } from "@/components/LocaleProvider";
import { MOTION_TOKENS } from "@/components/ui/motion";
import { catalogPricingTierOptions, catalogSortOptions } from "@/lib/catalog-widget-options";
import { cn } from "@/lib/utils";
import type { CatalogPricingTierFilter, CatalogUrlState, Market } from "@/lib/catalog-url";

export const cardListVariants = {
  hidden: {},
  show: {
    transition: {
      staggerChildren: MOTION_TOKENS.stagger.staggerChildren - 0.005,
      delayChildren: MOTION_TOKENS.stagger.delayChildren,
    },
  },
};

export const cardItemVariants = {
  hidden: { opacity: 0, y: 12, scale: 0.995 },
  show: {
    opacity: 1,
    y: 0,
    scale: 1,
    transition: { duration: MOTION_TOKENS.duration.base, ease: MOTION_TOKENS.easeSoft },
  },
};

export function SortDropdown({
  value,
  onChange,
  variant = "sidebar",
}: {
  value: string;
  onChange: (next: string) => void;
  variant?: "sidebar" | "toolbar";
}) {
  const { locale, t } = useLocaleContext();
  const sortOptions = useMemo(() => catalogSortOptions(locale), [locale]);
  const active = sortOptions.find((o) => o.value === value) ?? sortOptions[0];
  const isToolbar = variant === "toolbar";
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          type="button"
          variant="outline"
          className={cn(
            "h-10 justify-between font-normal shadow-sm",
            isToolbar ? "min-w-[10.5rem] max-w-full rounded-xl px-3" : "mt-2 w-full rounded-2xl",
          )}
          aria-label={t("catalog.widgets.sortAria", { label: active.label })}
        >
          <span className="min-w-0 truncate text-start">{active.label}</span>
          <ChevronsUpDown className="size-4 shrink-0 opacity-55" aria-hidden />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent
        align="start"
        className="w-[var(--radix-dropdown-menu-trigger-width)] min-w-[13rem] p-1.5"
      >
        <DropdownMenuLabel>{t("catalog.widgets.sortMenu")}</DropdownMenuLabel>
        <DropdownMenuRadioGroup value={value} onValueChange={onChange}>
          {sortOptions.map((o) => (
            <DropdownMenuRadioItem key={o.value} value={o.value} className="cursor-pointer">
              {o.label}
            </DropdownMenuRadioItem>
          ))}
        </DropdownMenuRadioGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

export function ListRowSkeleton() {
  return (
    <li>
      <Card
        size="sm"
        className="flex flex-col items-stretch gap-0 overflow-hidden py-0 shadow-sm ring-1 ring-elevated-ring md:flex-row"
      >
        <Skeleton className="aspect-[4/3] w-full shrink-0 rounded-none md:w-72" />
        <div className="flex min-w-0 flex-1 flex-col gap-0">
          <div className="flex items-center justify-between gap-3 border-b border-border/50 px-3 py-3 sm:px-4 md:px-5">
            <Skeleton className="h-4 w-[70%] rounded-md" />
            <div className="flex items-center gap-1.5">
              <Skeleton className="size-8 rounded-lg" />
              <Skeleton className="size-8 rounded-lg" />
            </div>
          </div>
          <div className="flex flex-1 items-start px-3 py-3 sm:px-4 md:px-5">
            <div className="flex w-full flex-wrap gap-1.5">
              <Skeleton className="h-6 w-24 rounded-xl" />
              <Skeleton className="h-6 w-20 rounded-xl" />
              <Skeleton className="h-6 w-28 rounded-xl" />
            </div>
          </div>
          <div className="border-t border-border/50 px-3 py-2.5 sm:px-4 md:px-5">
            <Skeleton className="h-8 w-28 rounded-lg" />
          </div>
        </div>
      </Card>
    </li>
  );
}

export function CatalogCardImage({
  images,
  displayImages: displayImagesProp,
  lqipSrc,
  alt,
  eager,
  sold,
}: {
  images: string[];
  /** Если задано (например батч из родителя), не вызываем отдельный прокси-хук на карточку. */
  displayImages?: string[];
  /** LQIP через /api/images?size=blur — снижает CLS до загрузки thumb. */
  lqipSrc?: string;
  alt: string;
  eager: boolean;
  sold?: boolean;
}) {
  const { t } = useLocaleContext();
  const hooked = useProxiedCatalogThumbUrls(displayImagesProp != null ? [] : images);
  const displayImages = displayImagesProp ?? hooked;
  const [idx, setIdx] = useState(0);
  const canCycle = displayImages.length > 1;

  useEffect(() => {
    setIdx(0);
  }, [images]);

  const src = displayImages[idx] ?? displayImages[0] ?? "";
  const [mainLoaded, setMainLoaded] = useState(false);
  useEffect(() => {
    setMainLoaded(false);
  }, [src]);

  if (!src) {
    return (
      <div className="flex size-full items-center justify-center bg-muted/40 px-2 text-center text-xs text-muted-foreground">
        {catalogCardImagePlaceholder(images.length > 0)}
      </div>
    );
  }

  return (
    <div
      className="relative size-full overflow-hidden bg-muted/30"
      onMouseEnter={() => {
        if (canCycle) setIdx(0);
      }}
      onMouseLeave={() => {
        setIdx(0);
      }}
    >
      {lqipSrc ? (
        // eslint-disable-next-line @next/next/no-img-element -- tiny LQIP from our CDN proxy
        <img
          src={lqipSrc}
          alt=""
          aria-hidden
          className={cn(
            "absolute inset-0 size-full scale-110 object-cover object-center blur-md transition-opacity duration-300",
            mainLoaded ? "opacity-0" : "opacity-100",
          )}
          decoding="async"
          loading="eager"
        />
      ) : null}
      <Image
        src={src}
        alt={alt}
        width={800}
        height={520}
        sizes="(min-width: 1024px) 320px, (min-width: 768px) 288px, 44vw"
        className={cn(
          "relative h-full w-full object-cover object-center transition-opacity duration-300",
          mainLoaded || !lqipSrc ? "opacity-100" : "opacity-0",
        )}
        loading={eager ? "eager" : "lazy"}
        fetchPriority={eager ? "high" : "auto"}
        decoding="async"
        unoptimized
        onLoad={() => setMainLoaded(true)}
        onError={() => setMainLoaded(true)}
      />
      {sold ? (
        <div className="pointer-events-none absolute inset-0 flex items-center justify-center bg-black/58 px-3">
          <p className="text-center text-sm font-semibold leading-snug text-white drop-shadow-md sm:text-base">
            {t("catalog.card.soldBadge")}
          </p>
        </div>
      ) : null}
    </div>
  );
}

export function RangeBlock({
  state,
  navigate,
  market,
}: {
  state: CatalogUrlState;
  navigate: (s: CatalogUrlState) => void;
  market: Market;
}) {
  const { locale, t } = useLocaleContext();
  const pricingTierOptions = useMemo(() => catalogPricingTierOptions(locale), [locale]);
  const [draft, setDraft] = useState({
    price_from: state.price_from,
    price_to: state.price_to,
    mileage_from: state.mileage_from,
    mileage_to: state.mileage_to,
    year_from: state.year_from,
    year_to: state.year_to,
    engine_cc_from: state.engine_cc_from,
    engine_cc_to: state.engine_cc_to,
    passable_only: state.passable_only,
  });
  useEffect(() => {
    setDraft({
      price_from: state.price_from,
      price_to: state.price_to,
      mileage_from: state.mileage_from,
      mileage_to: state.mileage_to,
      year_from: state.year_from,
      year_to: state.year_to,
      engine_cc_from: state.engine_cc_from,
      engine_cc_to: state.engine_cc_to,
      passable_only: state.passable_only,
    });
  }, [
    state.price_from,
    state.price_to,
    state.mileage_from,
    state.mileage_to,
    state.year_from,
    state.year_to,
    state.engine_cc_from,
    state.engine_cc_to,
    state.passable_only,
  ]);
  const apply = () => {
    navigate({
      ...state,
      ...draft,
      page: 1,
    });
  };
  const setPricingTier = (raw: string) => {
    const tier: CatalogPricingTierFilter =
      raw === "full_customs" || raw === "korea_land_only" || raw === "price_on_request" ? raw : "";
    navigate({
      ...state,
      pricing_tier: tier,
      customs_included_only: tier === "full_customs" ? false : state.customs_included_only,
      page: 1,
    });
  };

  return (
    <>
      {market === "korea" ? (
        <div className="mb-1 space-y-3 rounded-xl border border-border/80 bg-muted/15 px-3 py-3 dark:bg-muted/10">
          <div>
            <span className="text-sm font-medium text-foreground">{t("catalog.widgets.pricingTitle")}</span>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button
                  type="button"
                  variant="outline"
                  className="mt-1.5 h-10 w-full justify-between rounded-2xl font-normal"
                  aria-label={t("catalog.widgets.pricingAria", {
                    label:
                      pricingTierOptions.find((o) => o.value === (state.pricing_tier || "__any__"))?.label ??
                      t("catalog.widgets.tierAny"),
                  })}
                >
                  <span className="min-w-0 truncate text-start">
                    {pricingTierOptions.find((o) => o.value === (state.pricing_tier || "__any__"))?.label ??
                      t("catalog.widgets.tierAny")}
                  </span>
                  <ChevronsUpDown className="size-4 shrink-0 opacity-55" aria-hidden />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent
                align="start"
                className="w-[var(--radix-dropdown-menu-trigger-width)] min-w-[13rem] max-w-[min(100vw-2rem,24rem)] p-1.5"
              >
                <DropdownMenuLabel>{t("catalog.widgets.pricingTitle")}</DropdownMenuLabel>
                <DropdownMenuRadioGroup
                  value={state.pricing_tier || "__any__"}
                  onValueChange={(v) => setPricingTier(v === "__any__" ? "" : v)}
                >
                  {pricingTierOptions.map((o) => (
                    <DropdownMenuRadioItem key={o.value} value={o.value} className="cursor-pointer">
                      {o.label}
                    </DropdownMenuRadioItem>
                  ))}
                </DropdownMenuRadioGroup>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
          <label
            className={cn(
              "flex cursor-pointer items-start justify-between gap-2 rounded-xl border px-3 py-2.5 text-sm leading-snug shadow-sm",
              state.pricing_tier === "full_customs"
                ? "border-border/60 bg-muted/10 text-muted-foreground"
                : "border-border bg-muted/20",
            )}
          >
            <span className="inline-flex items-start gap-2">
              <Checkbox
                checked={state.customs_included_only}
                disabled={state.pricing_tier === "full_customs"}
                onCheckedChange={(v) =>
                  navigate({ ...state, customs_included_only: Boolean(v), page: 1 })
                }
                className="mt-0.5 shrink-0"
              />
              <span>
                {t("catalog.widgets.customsInPrice")}
                {state.pricing_tier === "full_customs" ? (
                  <span className="mt-1 block text-xs font-normal text-muted-foreground">
                    {t("catalog.widgets.customsFromTierHint")}
                  </span>
                ) : null}
              </span>
            </span>
            <Tooltip>
              <TooltipTrigger asChild>
                <button
                  type="button"
                  className="inline-flex shrink-0 text-muted-foreground disabled:opacity-40"
                  aria-label={t("catalog.widgets.customsInPriceAria")}
                  disabled={state.pricing_tier === "full_customs"}
                  onClick={(e) => e.preventDefault()}
                >
                  <CircleHelp className="size-4" />
                </button>
              </TooltipTrigger>
              <TooltipContent side="top" className="max-w-[20rem]">
                {t("catalog.widgets.customsInPriceTip")}
              </TooltipContent>
            </Tooltip>
          </label>
        </div>
      ) : null}
      <div className="grid grid-cols-1 gap-2 text-sm min-[420px]:grid-cols-2">
        <Input
          placeholder={t("catalog.widgets.priceFrom")}
          value={draft.price_from}
          onChange={(e) => setDraft((d) => ({ ...d, price_from: e.target.value }))}
          className="focus-visible:ring-2 focus-visible:ring-inset"
        />
        <Input
          placeholder={t("catalog.widgets.priceTo")}
          value={draft.price_to}
          onChange={(e) => setDraft((d) => ({ ...d, price_to: e.target.value }))}
          className="focus-visible:ring-2 focus-visible:ring-inset"
        />
        <Input
          placeholder={t("catalog.widgets.mileageFrom")}
          value={draft.mileage_from}
          onChange={(e) => setDraft((d) => ({ ...d, mileage_from: e.target.value }))}
          className="focus-visible:ring-2 focus-visible:ring-inset"
        />
        <Input
          placeholder={t("catalog.widgets.mileageTo")}
          value={draft.mileage_to}
          onChange={(e) => setDraft((d) => ({ ...d, mileage_to: e.target.value }))}
          className="focus-visible:ring-2 focus-visible:ring-inset"
        />
        <Input
          placeholder={t("catalog.widgets.yearFrom")}
          value={draft.year_from}
          onChange={(e) => setDraft((d) => ({ ...d, year_from: e.target.value }))}
          className="focus-visible:ring-2 focus-visible:ring-inset"
        />
        <Input
          placeholder={t("catalog.widgets.yearTo")}
          value={draft.year_to}
          onChange={(e) => setDraft((d) => ({ ...d, year_to: e.target.value }))}
          className="focus-visible:ring-2 focus-visible:ring-inset"
        />
        <Input
          placeholder={t("catalog.widgets.ccFrom")}
          value={draft.engine_cc_from}
          onChange={(e) => setDraft((d) => ({ ...d, engine_cc_from: e.target.value }))}
          className="focus-visible:ring-2 focus-visible:ring-inset"
        />
        <Input
          placeholder={t("catalog.widgets.ccTo")}
          value={draft.engine_cc_to}
          onChange={(e) => setDraft((d) => ({ ...d, engine_cc_to: e.target.value }))}
          className="focus-visible:ring-2 focus-visible:ring-inset"
        />
      </div>
      <label className="mt-2 flex cursor-pointer items-start justify-between gap-2 rounded-xl border border-border bg-muted/20 px-3 py-2.5 text-sm leading-snug shadow-sm">
        <span className="inline-flex items-start gap-2">
          <Checkbox
            checked={draft.passable_only}
            onCheckedChange={(v) => setDraft((d) => ({ ...d, passable_only: Boolean(v) }))}
            className="mt-0.5 shrink-0"
          />
          {t("catalog.widgets.passableOnly")}
        </span>
        <Tooltip>
          <TooltipTrigger asChild>
            <button
              type="button"
              className="inline-flex shrink-0 text-muted-foreground"
              aria-label={t("catalog.widgets.passableAria")}
              onClick={(e) => e.preventDefault()}
            >
              <CircleHelp className="size-4" />
            </button>
          </TooltipTrigger>
          <TooltipContent side="top">{t("catalog.widgets.passableTip")}</TooltipContent>
        </Tooltip>
      </label>
      <Button type="button" onClick={apply} className="mt-2 w-full" size="sm">
        {t("catalog.widgets.applyRanges")}
      </Button>
    </>
  );
}
