"use client";

import Image from "next/image";
import { useEffect, useState } from "react";
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
import { MOTION_TOKENS } from "@/components/ui/motion";
import { cn } from "@/lib/utils";
import type { CatalogPricingTierFilter, CatalogUrlState, Market } from "@/lib/catalog-url";

export const SORT_OPTIONS: { value: string; label: string }[] = [
  { value: "date_new", label: "Сначала новые" },
  { value: "date_old", label: "Сначала старые" },
  { value: "year_new", label: "Год: новее" },
  { value: "year_old", label: "Год: старше" },
  { value: "price_low", label: "Цена: дешевле" },
  { value: "price_high", label: "Цена: дороже" },
  { value: "mileage_low", label: "Пробег: меньше" },
  { value: "mileage_high", label: "Пробег: больше" },
];

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

export function SortDropdown({ value, onChange }: { value: string; onChange: (next: string) => void }) {
  const active = SORT_OPTIONS.find((o) => o.value === value) ?? SORT_OPTIONS[0];
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          type="button"
          variant="outline"
          className="mt-2 h-10 w-full justify-between rounded-2xl font-normal"
          aria-label={`Сортировка списка: ${active.label}`}
        >
          <span className="min-w-0 truncate text-start">{active.label}</span>
          <ChevronsUpDown className="size-4 shrink-0 opacity-55" aria-hidden />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent
        align="start"
        className="w-[var(--radix-dropdown-menu-trigger-width)] min-w-[13rem] p-1.5"
      >
        <DropdownMenuLabel>Сортировка списка</DropdownMenuLabel>
        <DropdownMenuRadioGroup value={value} onValueChange={onChange}>
          {SORT_OPTIONS.map((o) => (
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
        className="flex flex-col items-stretch gap-0 overflow-hidden py-0 shadow-sm ring-1 ring-border/60 sm:min-h-[13rem] sm:flex-row"
      >
        <Skeleton className="h-52 w-full shrink-0 rounded-none sm:h-auto sm:w-60 sm:min-h-[13rem] md:w-72" />
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
  alt,
  eager,
  sold,
}: {
  images: string[];
  alt: string;
  eager: boolean;
  sold?: boolean;
}) {
  const [idx, setIdx] = useState(0);
  const canCycle = images.length > 1;

  useEffect(() => {
    setIdx(0);
  }, [images]);

  const src = images[idx] ?? images[0] ?? "";
  if (!src) {
    return (
      <div className="flex size-full items-center justify-center px-2 text-center text-xs text-muted-foreground">
        Нет фото
      </div>
    );
  }

  return (
    <div
      className="relative size-full"
      onMouseEnter={() => {
        if (canCycle) setIdx(0);
      }}
      onMouseLeave={() => {
        setIdx(0);
      }}
    >
      <Image
        src={src}
        alt={alt}
        width={448}
        height={288}
        sizes="(min-width: 1024px) 224px, 44vw"
        className="h-full w-full object-cover object-center"
        loading={eager ? "eager" : "lazy"}
        fetchPriority={eager ? "high" : "auto"}
        decoding="async"
        unoptimized
      />
      {sold ? (
        <div className="pointer-events-none absolute inset-0 flex items-center justify-center bg-black/58 px-3">
          <p className="text-center text-sm font-semibold leading-snug text-white drop-shadow-md sm:text-base">
            Автомобиль продан
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
            <span className="text-sm font-medium text-foreground">Оценка цены</span>
            <div className="relative mt-1.5">
              <select
                aria-label="Фильтр по типу оценки цены"
                className="h-9 w-full appearance-none rounded-2xl border border-border bg-background px-3 pe-10 text-sm shadow-sm outline-none transition-[box-shadow,border-color] focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/25"
                value={state.pricing_tier || ""}
                onChange={(e) => setPricingTier(e.target.value)}
              >
                <option value="">Любая</option>
                <option value="full_customs">Под ключ (с таможней РФ)</option>
                <option value="korea_land_only">Без таможни РФ (Корея и логистика)</option>
                <option value="price_on_request">Цена по запросу</option>
              </select>
              <ChevronsUpDown className="pointer-events-none absolute end-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground/80" />
            </div>
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
                В цене уже учтена таможня РФ
                {state.pricing_tier === "full_customs" ? (
                  <span className="mt-1 block text-xs font-normal text-muted-foreground">
                    Это уже следует из фильтра «Под ключ».
                  </span>
                ) : null}
              </span>
            </span>
            <Tooltip>
              <TooltipTrigger asChild>
                <button
                  type="button"
                  className="inline-flex shrink-0 text-muted-foreground disabled:opacity-40"
                  aria-label="Пояснение: таможня в цене"
                  disabled={state.pricing_tier === "full_customs"}
                  onClick={(e) => e.preventDefault()}
                >
                  <CircleHelp className="size-4" />
                </button>
              </TooltipTrigger>
              <TooltipContent side="top" className="max-w-[20rem]">
                Показываются объявления, где расчёт итога включает пошлины и сборы таможни РФ (слой «под ключ» по
                данным каталога).
              </TooltipContent>
            </Tooltip>
          </label>
        </div>
      ) : null}
      <div className="grid grid-cols-1 gap-2 text-sm min-[420px]:grid-cols-2">
        <Input
          placeholder="Цена от"
          value={draft.price_from}
          onChange={(e) => setDraft((d) => ({ ...d, price_from: e.target.value }))}
          className="focus-visible:ring-2 focus-visible:ring-inset"
        />
        <Input
          placeholder="Цена до"
          value={draft.price_to}
          onChange={(e) => setDraft((d) => ({ ...d, price_to: e.target.value }))}
          className="focus-visible:ring-2 focus-visible:ring-inset"
        />
        <Input
          placeholder="Пробег от"
          value={draft.mileage_from}
          onChange={(e) => setDraft((d) => ({ ...d, mileage_from: e.target.value }))}
          className="focus-visible:ring-2 focus-visible:ring-inset"
        />
        <Input
          placeholder="Пробег до"
          value={draft.mileage_to}
          onChange={(e) => setDraft((d) => ({ ...d, mileage_to: e.target.value }))}
          className="focus-visible:ring-2 focus-visible:ring-inset"
        />
        <Input
          placeholder="Год от"
          value={draft.year_from}
          onChange={(e) => setDraft((d) => ({ ...d, year_from: e.target.value }))}
          className="focus-visible:ring-2 focus-visible:ring-inset"
        />
        <Input
          placeholder="Год до"
          value={draft.year_to}
          onChange={(e) => setDraft((d) => ({ ...d, year_to: e.target.value }))}
          className="focus-visible:ring-2 focus-visible:ring-inset"
        />
        <Input
          placeholder="Объём от (см³)"
          value={draft.engine_cc_from}
          onChange={(e) => setDraft((d) => ({ ...d, engine_cc_from: e.target.value }))}
          className="focus-visible:ring-2 focus-visible:ring-inset"
        />
        <Input
          placeholder="Объём до (см³)"
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
          Только проходные авто
        </span>
        <Tooltip>
          <TooltipTrigger asChild>
            <button
              type="button"
              className="inline-flex shrink-0 text-muted-foreground"
              aria-label="Что такое проходные авто"
              onClick={(e) => e.preventDefault()}
            >
              <CircleHelp className="size-4" />
            </button>
          </TooltipTrigger>
          <TooltipContent side="top">
            «Проходными» считаются автомобили возрастом от 3 до 5 лет. Для них обычно действуют
            льготные таможенные тарифы.
          </TooltipContent>
        </Tooltip>
      </label>
      <Button type="button" onClick={apply} className="mt-2 w-full" size="sm">
        Применить диапазоны
      </Button>
    </>
  );
}
