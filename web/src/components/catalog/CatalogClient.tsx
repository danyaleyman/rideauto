"use client";

import Image from "next/image";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { AnimatePresence, motion } from "framer-motion";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  catalogStateKey,
  parseCatalogUrl,
  PER_PAGE,
  stateToBrowserUrl,
  type CatalogUrlState,
  type Market,
  toApiSearchParams,
  toFacetApiParams,
} from "@/lib/catalog-url";
import { fetchCatalogDailyAdditions, fetchFacetsClient, fetchSearchClient } from "@/lib/client-api";
import { extractCarImageUrls } from "@/lib/car-images";
import { imageUrlDedupeKey } from "@/lib/car-gallery-images";
import { getCarPageAbsoluteUrl } from "@/lib/car-url";
import { isCatalogListedToday } from "@/lib/catalog-listed-today";
import { isCatalogDiagEnabled, sendCatalogDiagEvent } from "@/lib/catalog-diagnostics";
import { asStr, formatKm, formatRegYearMonth } from "@/lib/car-detail-data";
import { formatCatalogCardPrice } from "@/lib/format-price";
import { useFavorites } from "@/hooks/use-favorites";
import { MarketSegmentedControl } from "@/components/catalog/MarketSegmentedControl";
import { cn } from "@/lib/utils";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Pagination,
  PaginationContent,
  PaginationEllipsis,
  PaginationItem,
} from "@/components/ui/pagination";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import type { LucideIcon } from "lucide-react";
import {
  CalendarDays,
  CircleHelp,
  Check,
  ChevronsUpDown,
  ChevronLeft,
  ChevronRight,
  Copy,
  Fuel,
  Gauge,
  Heart,
  Settings2,
  Sparkles,
  Zap,
} from "lucide-react";
import type { FacetRow, FacetsResponse, SearchResponse, SlimCar } from "@/lib/types";

/** Номера страниц с «…» для shadcn Pagination. */
function visiblePageItems(page: number, total: number): Array<number | "ellipsis"> {
  if (total < 1) return [];
  if (total === 1) return [1];
  const set = new Set<number>();
  set.add(1);
  set.add(total);
  for (let p = page - 1; p <= page + 1; p++) {
    if (p >= 1 && p <= total) set.add(p);
  }
  const sorted = [...set].sort((a, b) => a - b);
  const out: Array<number | "ellipsis"> = [];
  for (let i = 0; i < sorted.length; i++) {
    if (i > 0 && sorted[i] - sorted[i - 1] > 1) out.push("ellipsis");
    out.push(sorted[i]);
  }
  return out;
}

function previewImageUrls(car: SlimCar): string[] {
  const all = extractCarImageUrls((car.data ?? {}) as Record<string, unknown>);
  if (!all.length) return [];
  const seen = new Set<string>();
  const ordered: string[] = [];
  for (const u of all) {
    const t = u.trim();
    const k = imageUrlDedupeKey(t);
    if (seen.has(k)) continue;
    seen.add(k);
    ordered.push(t);
  }
  return ordered.slice(0, 4);
}

function carsAddedTodayLabel(n: number): string {
  if (n === 0) return "Сегодня новых записей нет";
  const n10 = n % 10;
  const n100 = n % 100;
  let word: string;
  if (n100 >= 11 && n100 <= 19) word = "автомобилей";
  else if (n10 === 1) word = "автомобиль";
  else if (n10 >= 2 && n10 <= 4) word = "автомобиля";
  else word = "автомобилей";
  return `${n.toLocaleString("ru-RU")} ${word} добавлено сегодня`;
}

type PassabilityStatus = "passable" | "young" | "old";

function facetRowLabel(row: FacetRow): string {
  const label = String(row.label ?? "").trim();
  return label || row.value;
}

function groupFacetRows(rows: FacetRow[]): Array<{ label: string; values: string[]; count: number }> {
  const grouped = new Map<string, { label: string; values: Set<string>; count: number }>();
  for (const row of rows) {
    const label = facetRowLabel(row).trim();
    if (!label) continue;
    const key = label.toLowerCase().replace(/\s+/g, " ");
    const rawValues = Array.isArray(row.values) && row.values.length ? row.values : [row.value];
    const bucket = grouped.get(key) ?? { label, values: new Set<string>(), count: 0 };
    for (const v of rawValues) {
      const t = String(v ?? "").trim();
      if (t) bucket.values.add(t);
    }
    bucket.count += Number(row.count || 0);
    grouped.set(key, bucket);
  }
  const out = Array.from(grouped.values()).map((b) => ({
    label: b.label,
    values: Array.from(b.values),
    count: b.count,
  }));
  out.sort((a, b) => a.label.localeCompare(b.label));
  return out;
}

function parseYmValue(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) {
    const iv = Math.trunc(value);
    if (iv >= 190001 && iv % 100 >= 1 && iv % 100 <= 12) return iv;
  }
  const s = String(value ?? "").trim();
  if (!s) return null;
  const digits = s.replace(/[^\d]/g, "");
  if (digits.length < 6) return null;
  const y = Number.parseInt(digits.slice(0, 4), 10);
  const m = Number.parseInt(digits.slice(4, 6), 10);
  if (!Number.isFinite(y) || !Number.isFinite(m) || y <= 1900 || m < 1 || m > 12) return null;
  return y * 100 + m;
}

function carPassabilityStatus(data: Record<string, unknown>): PassabilityStatus | null {
  const ym = parseYmValue(data.yearMonth) ?? parseYmValue(data.year_month) ?? parseYmValue(data.year);
  if (!ym) return null;
  const now = new Date();
  const nowYm = now.getUTCFullYear() * 100 + (now.getUTCMonth() + 1);
  const nowMonths = Math.floor(nowYm / 100) * 12 + (nowYm % 100 - 1);
  const carMonths = Math.floor(ym / 100) * 12 + (ym % 100 - 1);
  const ageMonths = nowMonths - carMonths;
  if (ageMonths <= 36) return "young";
  if (ageMonths <= 59) return "passable";
  return "old";
}

/** Чипы как на странице авто: дата регистрации гг/мм (или год), пробег, топливо — без дублирования заголовка. */
function formatDisplacementLiters(cc: number): string {
  const liters = cc / 1000;
  const rounded = Math.round(liters * 10) / 10;
  const isInt = Math.abs(rounded - Math.round(rounded)) < 1e-9;
  const shown = isInt ? String(Math.round(rounded)) : String(rounded).replace(".", ",");
  const n = rounded;
  const last = Math.floor(n) % 10;
  const last2 = Math.floor(n) % 100;
  const word =
    !isInt
      ? "литра"
      : last === 1 && last2 !== 11
        ? "литр"
        : last >= 2 && last <= 4 && !(last2 >= 12 && last2 <= 14)
          ? "литра"
          : "литров";
  return `${shown} ${word}`;
}

function catalogCardAttributeChips(
  data: Record<string, unknown>,
  yearNum?: number | null,
): { key: string; label: string; Icon: LucideIcon }[] {
  const chips: { key: string; label: string; Icon: LucideIcon }[] = [];
  const ym = formatRegYearMonth(data.yearMonth) ?? formatRegYearMonth(data.year);
  if (ym) chips.push({ key: "ym", label: ym, Icon: CalendarDays });
  else if (yearNum != null && Number.isFinite(yearNum) && yearNum > 0) {
    chips.push({ key: "y", label: String(Math.round(yearNum)), Icon: CalendarDays });
  }
  const km = formatKm(data.km_age);
  if (km) chips.push({ key: "km", label: km, Icon: Gauge });
  const fuel = asStr(data.engine_type) ?? asStr(data.fuel);
  if (fuel) chips.push({ key: "fuel", label: fuel, Icon: Fuel });
  const fuelLower = (fuel || "").toLowerCase();
  const isElectricFuel =
    fuelLower.includes("electric") ||
    fuelLower.includes("ev") ||
    fuelLower.includes("электро") ||
    fuelLower.includes("전기");
  const ccRaw = data.displacement ?? data.displacement_cc ?? data.engine_volume;
  const ccNum =
    typeof ccRaw === "number"
      ? Math.trunc(ccRaw)
      : Number.parseInt(String(ccRaw ?? "").replace(/[^\d]/g, ""), 10);
  if (!isElectricFuel && Number.isFinite(ccNum) && ccNum > 0) {
    chips.push({ key: "cc", label: formatDisplacementLiters(ccNum), Icon: Settings2 });
  }
  const hpRaw = data.power_hp ?? data.power ?? data.hp;
  const hpNum =
    typeof hpRaw === "number"
      ? Math.trunc(hpRaw)
      : Number.parseInt(String(hpRaw ?? "").replace(/[^\d]/g, ""), 10);
  if (Number.isFinite(hpNum) && hpNum > 0) {
    chips.push({ key: "hp", label: `${hpNum} л.с.`, Icon: Zap });
  }
  return chips;
}

function cardOverlayBadges(
  data: Record<string, unknown>,
  yearNum?: number | null,
  market: Market = "korea",
): string[] {
  const out: string[] = [];
  if (yearNum && Number.isFinite(yearNum)) out.push(String(Math.trunc(yearNum)));
  if (market === "china") return out.slice(0, 1);
  return out.slice(0, 4);
}

function FacetMultiDropdown({
  label,
  rows,
  selected,
  onToggle,
  disabled,
}: {
  label: string;
  rows: FacetRow[];
  selected: Set<string>;
  onToggle: (values: string[]) => void;
  disabled?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const groupedRows = useMemo(() => groupFacetRows(rows), [rows]);
  const filtered = useMemo(
    () =>
      !q.trim()
        ? groupedRows
        : groupedRows.filter((r) => r.label.toLowerCase().includes(q.trim().toLowerCase())),
    [groupedRows, q],
  );
  const n = groupedRows.filter((r) => r.values.some((v) => selected.has(v))).length;
  return (
    <DropdownMenu
      open={open}
      onOpenChange={(o) => {
        setOpen(o);
        if (!o) setQ("");
      }}
    >
      <DropdownMenuTrigger asChild>
        <Button
          type="button"
          variant="outline"
          disabled={disabled || !groupedRows.length}
          className="h-10 w-full justify-between gap-2 rounded-2xl px-3.5 font-normal"
        >
          <span className="min-w-0 text-start [overflow-wrap:anywhere]">
            {label}
            {n > 0 ? (
              <span className="ms-1 tabular-nums text-muted-foreground">({n})</span>
            ) : null}
          </span>
          <ChevronsUpDown className="size-4 shrink-0 opacity-50" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent
        align="start"
        className="max-h-[min(24rem,70vh)] w-[var(--radix-dropdown-menu-trigger-width)] min-w-[12rem] overflow-hidden p-0 shadow-lg"
        onCloseAutoFocus={(e) => e.preventDefault()}
      >
        <div className="border-b border-border p-2">
          <Input
            placeholder="Поиск…"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            className="h-8 rounded-xl"
            onPointerDown={(e) => e.stopPropagation()}
            onKeyDown={(e) => e.stopPropagation()}
          />
        </div>
        <DropdownMenuLabel className="px-3 py-2 text-xs font-normal text-muted-foreground">
          Можно выбрать несколько
        </DropdownMenuLabel>
        <div className="max-h-60 overflow-y-auto overscroll-contain p-1.5 pt-0">
          {filtered.length === 0 ? (
            <p className="px-3 py-6 text-center text-sm text-muted-foreground">Нет совпадений</p>
          ) : (
            filtered.map((r) => (
              <DropdownMenuCheckboxItem
                key={r.label}
                checked={r.values.some((v) => selected.has(v))}
                onCheckedChange={() => onToggle(r.values)}
                className="cursor-text rounded-xl select-text [&>span:last-child]:ps-2"
              >
                <span className="min-w-0 flex-1 select-text [overflow-wrap:anywhere]">{r.label}</span>
                <span className="ms-1 shrink-0 tabular-nums text-xs text-muted-foreground">
                  {r.count.toLocaleString("ru-RU")}
                </span>
              </DropdownMenuCheckboxItem>
            ))
          )}
        </div>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

const COLOR_SWATCH_BY_NAME: Array<{ re: RegExp; className: string }> = [
  { re: /(бел|white)/i, className: "bg-white ring-1 ring-border" },
  { re: /(черн|black)/i, className: "bg-zinc-900 ring-1 ring-zinc-700" },
  { re: /(сер|gray|grey|silver|сереб)/i, className: "bg-zinc-400" },
  { re: /(син|blue)/i, className: "bg-blue-500" },
  { re: /(крас|red)/i, className: "bg-red-500" },
  { re: /(зелен|green)/i, className: "bg-emerald-500" },
  { re: /(желт|gold|orange|оранж)/i, className: "bg-amber-400" },
  { re: /(корич|brown|beige|беж)/i, className: "bg-amber-700" },
  { re: /(фиолет|purple|violet)/i, className: "bg-violet-500" },
];

function colorSwatchClass(colorName: string): string {
  const match = COLOR_SWATCH_BY_NAME.find((item) => item.re.test(colorName));
  return match?.className ?? "bg-gradient-to-br from-slate-200 to-slate-500";
}

function SortDropdown({
  value,
  onChange,
}: {
  value: string;
  onChange: (next: string) => void;
}) {
  const active = SORT_OPTIONS.find((o) => o.value === value) ?? SORT_OPTIONS[0];
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button type="button" variant="outline" className="mt-2 h-10 w-full justify-between rounded-2xl font-normal">
          <span className="min-w-0 truncate text-start">{active.label}</span>
          <ChevronsUpDown className="size-4 shrink-0 opacity-55" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="w-[var(--radix-dropdown-menu-trigger-width)] min-w-[13rem] p-1.5">
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

function ListRowSkeleton() {
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

function CatalogCardImage({
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

function RangeBlock({
  state,
  navigate,
}: {
  state: CatalogUrlState;
  navigate: (s: CatalogUrlState) => void;
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
  return (
    <>
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

const SORT_OPTIONS: { value: string; label: string }[] = [
  { value: "date_new", label: "Сначала новые" },
  { value: "date_old", label: "Сначала старые" },
  { value: "year_new", label: "Год: новее" },
  { value: "year_old", label: "Год: старше" },
  { value: "price_low", label: "Цена: дешевле" },
  { value: "price_high", label: "Цена: дороже" },
  { value: "mileage_low", label: "Пробег: меньше" },
  { value: "mileage_high", label: "Пробег: больше" },
];

const cardListVariants = {
  hidden: {},
  show: {
    transition: {
      staggerChildren: 0.035,
      delayChildren: 0.03,
    },
  },
};

const cardItemVariants = {
  hidden: { opacity: 0, y: 12, scale: 0.995 },
  show: {
    opacity: 1,
    y: 0,
    scale: 1,
    transition: { duration: 0.26, ease: [0.22, 1, 0.36, 1] as const },
  },
};

export function CatalogClient({
  initialSearch,
  ssrKey,
}: {
  initialSearch: SearchResponse;
  ssrKey: string;
}) {
  const router = useRouter();
  const sp = useSearchParams();
  const spStr = sp.toString();
  const diagEnabled = useMemo(() => isCatalogDiagEnabled(spStr), [spStr]);
  const state = useMemo(() => parseCatalogUrl(new URLSearchParams(spStr)), [spStr]);
  const key = useMemo(() => catalogStateKey(state), [state]);

  const [search, setSearch] = useState<SearchResponse>(initialSearch);
  const [facets, setFacets] = useState<FacetsResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [qDraft, setQDraft] = useState(state.q);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [dailyNewCount, setDailyNewCount] = useState<number | null>(null);
  const [dailyNewLoading, setDailyNewLoading] = useState(true);
  const facetsCacheRef = useRef<Map<string, FacetsResponse>>(new Map());
  const { toggle: toggleFavorite, isFavorite } = useFavorites();

  useEffect(() => {
    setQDraft(state.q);
  }, [state.q]);

  useEffect(() => {
    if (!spStr.trim()) {
      const qs = stateToBrowserUrl(parseCatalogUrl(new URLSearchParams()));
      router.replace(`/catalog?${qs}`, { scroll: false });
    }
  }, [spStr, router]);

  useEffect(() => {
    const ac = new AbortController();
    const market: Market = state.market;
    setDailyNewLoading(true);
    setDailyNewCount(null);
    (async () => {
      try {
        const r = await fetchCatalogDailyAdditions(market, ac.signal);
        if (ac.signal.aborted) return;
        setDailyNewCount(r.count);
      } catch {
        if (ac.signal.aborted) return;
        setDailyNewCount(null);
      } finally {
        if (!ac.signal.aborted) setDailyNewLoading(false);
      }
    })();
    return () => ac.abort();
  }, [state.market]);

  const navigate = useCallback(
    (next: CatalogUrlState) => {
      const qs = stateToBrowserUrl(next);
      sendCatalogDiagEvent(diagEnabled, "catalog_navigate", {
        from: spStr,
        to: qs,
        next_page: next.page,
        next_sort: next.sort,
      }, { market: state.market });
      router.push(qs ? `/catalog?${qs}` : "/catalog", { scroll: false });
    },
    [diagEnabled, router, spStr, state.market],
  );

  useEffect(() => {
    const nextQ = qDraft.trim();
    if (nextQ === state.q) return;
    if (nextQ.length > 0 && nextQ.length < 2) return;
    const t = window.setTimeout(() => {
      navigate({ ...state, q: nextQ, page: 1 });
    }, 450);
    return () => window.clearTimeout(t);
  }, [qDraft, state, navigate]);

  const facetState = useMemo(
    () => ({
      ...state,
      page: 1,
      // Facets are independent from sort; avoid refetch on sort switch.
      sort: "date_new",
    }),
    [state],
  );
  const facetKey = useMemo(() => catalogStateKey(facetState), [facetState]);

  useEffect(() => {
    const ac = new AbortController();
    (async () => {
      const started = Date.now();
      try {
        setErr(null);
        setLoading(true);
        const sq = toApiSearchParams(state);
        sendCatalogDiagEvent(diagEnabled, "catalog_search_start", {
          key,
          query: sq.toString(),
          page: state.page,
        }, { market: state.market });
        const searchP =
          key === ssrKey
            ? Promise.resolve(initialSearch)
            : fetchSearchClient(sq, { signal: ac.signal });
        const sRes = await searchP;
        if (ac.signal.aborted) return;
        setSearch(sRes);
        sendCatalogDiagEvent(diagEnabled, "catalog_search_ok", {
          key,
          duration_ms: Date.now() - started,
          total: sRes.meta?.total ?? null,
          result_len: sRes.result?.length ?? null,
        }, { market: state.market });
      } catch (e) {
        if (ac.signal.aborted) return;
        setErr(e instanceof Error ? e.message : "Ошибка загрузки");
        sendCatalogDiagEvent(diagEnabled, "catalog_search_failed", {
          key,
          duration_ms: Date.now() - started,
          error: e instanceof Error ? e.message : "unknown",
        }, { level: "error", market: state.market });
      } finally {
        if (!ac.signal.aborted) setLoading(false);
      }
    })();
    return () => {
      ac.abort();
    };
  }, [diagEnabled, key, ssrKey, state, initialSearch]);

  useEffect(() => {
    const cached = facetsCacheRef.current.get(facetKey);
    if (cached) {
      setFacets(cached);
      return;
    }
    const ac = new AbortController();
    (async () => {
      const started = Date.now();
      try {
        const fq = toFacetApiParams(facetState);
        sendCatalogDiagEvent(diagEnabled, "catalog_facets_start", {
          facet_key: facetKey,
          query: fq.toString(),
        }, { market: state.market });
        const fRes = await fetchFacetsClient(fq, { signal: ac.signal });
        if (ac.signal.aborted) return;
        facetsCacheRef.current.set(facetKey, fRes);
        setFacets(fRes);
        sendCatalogDiagEvent(diagEnabled, "catalog_facets_ok", {
          facet_key: facetKey,
          duration_ms: Date.now() - started,
          marks_len: fRes.marks?.length ?? null,
        }, { market: state.market });
      } catch (e) {
        console.error("facets fetch failed", e);
        sendCatalogDiagEvent(diagEnabled, "catalog_facets_failed", {
          facet_key: facetKey,
          duration_ms: Date.now() - started,
          error: e instanceof Error ? e.message : "unknown",
        }, { level: "error", market: state.market });
        // Keep previous facets on transient errors; if there were none, leave null (accordion shows skeletons).
      }
    })();
    return () => ac.abort();
  }, [diagEnabled, facetKey, facetState, state.market]);

  const toggle = (field: keyof CatalogUrlState, values: string | string[]) => {
    const cur = state[field];
    if (!Array.isArray(cur)) return;
    const vals = Array.isArray(values) ? values.filter(Boolean) : [values].filter(Boolean);
    if (!vals.length) return;
    const set = new Set(cur);
    const remove = vals.every((v) => set.has(v));
    for (const v of vals) {
      if (remove) set.delete(v);
      else set.add(v);
    }
    const arr = Array.from(set);
    const next: CatalogUrlState = { ...state, [field]: arr, page: 1 };
    if (field === "marks") {
      next.models = [];
      next.generations = [];
      next.trims = [];
    } else if (field === "models") {
      next.generations = [];
      next.trims = [];
    } else if (field === "generations") {
      next.trims = [];
    }
    sendCatalogDiagEvent(diagEnabled, "catalog_filter_toggle", {
      field,
      value: vals.join(","),
      selected_count: arr.length,
      current_page: state.page,
    }, { market: state.market });
    navigate(next);
  };

  const reset = () => {
    navigate({
      market: state.market,
      q: "",
      marks: [],
      models: [],
      generations: [],
      trims: [],
      body: [],
      fuel: [],
      trans: [],
      color: [],
      price_from: "",
      price_to: "",
      mileage_from: "",
      mileage_to: "",
      year_from: "",
      year_to: "",
      engine_cc_from: "",
      engine_cc_to: "",
      passable_only: false,
      power_hp_le_160: false,
      drive_awd: false,
      sort: "date_new",
      page: 1,
    });
  };

  const switchMarket = (market: CatalogUrlState["market"]) => {
    navigate({
      market,
      q: state.q,
      sort: state.sort,
      marks: [],
      models: [],
      generations: [],
      trims: [],
      body: [],
      fuel: [],
      trans: [],
      color: [],
      price_from: "",
      price_to: "",
      mileage_from: "",
      mileage_to: "",
      year_from: "",
      year_to: "",
      engine_cc_from: "",
      engine_cc_to: "",
      passable_only: false,
      power_hp_le_160: false,
      drive_awd: false,
      page: 1,
    });
  };

  const title =
    state.market === "china" ? "Автомобили из Китая" : "Автомобили из Кореи";

  const pages =
    search.meta.pages > 0
      ? search.meta.pages
      : Math.max(1, Math.ceil(search.meta.total / PER_PAGE));

  const pageItems = useMemo(() => visiblePageItems(state.page, pages), [state.page, pages]);

  const facetLabelByValue = useMemo(() => {
    const f = facets ?? {
      marks: [],
      models: [],
      generations: [],
      trims: [],
      bodies: [],
      fuels: [],
      transmissions: [],
      colors: [],
    };
    const map = new Map<string, string>();
    const allRows = [
      ...f.marks,
      ...f.models,
      ...f.generations,
      ...f.trims,
      ...f.bodies,
      ...f.fuels,
      ...f.transmissions,
      ...f.colors,
    ];
    for (const row of allRows) {
      map.set(row.value, facetRowLabel(row));
    }
    return map;
  }, [facets]);

  const activeChips = useMemo(() => {
    const withLabel = (v: string) => facetLabelByValue.get(v) ?? v;
    const chips: Array<{ key: keyof CatalogUrlState; label: string; value?: string }> = [];
    const pushDedupByLabel = (key: keyof CatalogUrlState, prefix: string, values: string[]) => {
      const seen = new Set<string>();
      for (const raw of values) {
        const shown = withLabel(raw);
        const marker = shown.toLowerCase();
        if (seen.has(marker)) continue;
        seen.add(marker);
        chips.push({ key, label: `${prefix}: ${shown}`, value: raw });
      }
    };
    pushDedupByLabel("marks", "Марка", state.marks);
    pushDedupByLabel("models", "Модель", state.models);
    pushDedupByLabel("generations", "Поколение", state.generations);
    pushDedupByLabel("trims", "Комплектация", state.trims);
    state.body.forEach((v) => chips.push({ key: "body", label: `Кузов: ${withLabel(v)}`, value: v }));
    state.fuel.forEach((v) => chips.push({ key: "fuel", label: `Топливо: ${withLabel(v)}`, value: v }));
    state.trans.forEach((v) => chips.push({ key: "trans", label: `КПП: ${withLabel(v)}`, value: v }));
    state.color.forEach((v) => chips.push({ key: "color", label: `Цвет: ${withLabel(v)}`, value: v }));
    if (state.drive_awd) chips.push({ key: "drive_awd", label: "Полный привод" });
    if (state.power_hp_le_160) chips.push({ key: "power_hp_le_160", label: "До 160 л.с." });
    if (state.passable_only) chips.push({ key: "passable_only", label: "Только проходные авто" });
    if (state.price_from) chips.push({ key: "price_from", label: `Цена от: ${state.price_from}` });
    if (state.price_to) chips.push({ key: "price_to", label: `Цена до: ${state.price_to}` });
    if (state.mileage_from) chips.push({ key: "mileage_from", label: `Пробег от: ${state.mileage_from}` });
    if (state.mileage_to) chips.push({ key: "mileage_to", label: `Пробег до: ${state.mileage_to}` });
    if (state.year_from) chips.push({ key: "year_from", label: `Год от: ${state.year_from}` });
    if (state.year_to) chips.push({ key: "year_to", label: `Год до: ${state.year_to}` });
    if (state.engine_cc_from) chips.push({ key: "engine_cc_from", label: `Объём от: ${state.engine_cc_from}` });
    if (state.engine_cc_to) chips.push({ key: "engine_cc_to", label: `Объём до: ${state.engine_cc_to}` });
    return chips;
  }, [state, facetLabelByValue]);

  const removeChip = (chip: { key: keyof CatalogUrlState; value?: string }) => {
    if (
      chip.key === "marks" ||
      chip.key === "models" ||
      chip.key === "generations" ||
      chip.key === "trims" ||
      chip.key === "body" ||
      chip.key === "fuel" ||
      chip.key === "trans" ||
      chip.key === "color"
    ) {
      if (!chip.value) return;
      const targetLabel = facetLabelByValue.get(chip.value) ?? chip.value;
      const cur = state[chip.key];
      if (!Array.isArray(cur)) return;
      const toRemove = cur.filter((v) => (facetLabelByValue.get(v) ?? v) === targetLabel);
      toggle(chip.key, toRemove.length ? toRemove : chip.value);
      return;
    }
    if (chip.key === "drive_awd") {
      navigate({ ...state, drive_awd: false, page: 1 });
      return;
    }
    if (chip.key === "power_hp_le_160") {
      navigate({ ...state, power_hp_le_160: false, page: 1 });
      return;
    }
    if (chip.key === "passable_only") {
      navigate({ ...state, passable_only: false, page: 1 });
      return;
    }
    navigate({ ...state, [chip.key]: "", page: 1 });
  };

  return (
    <div className="min-h-screen overflow-x-hidden bg-gradient-to-b from-muted/40 via-background to-background pb-10 pt-2 sm:pt-4">
      <div className="relative mx-auto min-w-0 max-w-[1440px] px-3 sm:px-6 lg:px-10">
        <div className="mb-5 flex min-w-0 rounded-2xl border border-border/50 bg-card/70 px-3 py-3 shadow-sm backdrop-blur-sm sm:mb-6 sm:px-5">
          <Breadcrumb className="min-w-0 flex-1">
            <BreadcrumbList className="flex-wrap gap-x-1 gap-y-1 sm:flex-nowrap">
              <BreadcrumbItem>
                <BreadcrumbLink asChild>
                  <Link href="/">Главная</Link>
                </BreadcrumbLink>
              </BreadcrumbItem>
              <BreadcrumbSeparator />
              <BreadcrumbItem className="min-w-0 max-w-full">
                <BreadcrumbPage className="line-clamp-2 break-words text-start font-medium [overflow-wrap:anywhere] sm:line-clamp-1">
                  Каталог
                </BreadcrumbPage>
              </BreadcrumbItem>
            </BreadcrumbList>
          </Breadcrumb>
        </div>

        {err ? (
          <div className="mb-4 rounded-xl border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive [overflow-wrap:anywhere]">
            {err} — проверьте{" "}
            <code className="break-all rounded bg-background/80 px-1">NEXT_PUBLIC_API_BASE</code> и доступность
            API.
          </div>
        ) : null}

        <div className="flex min-w-0 flex-col gap-6 lg:flex-row lg:items-start lg:gap-7">
          <aside className="w-full min-w-0 shrink-0 self-start lg:w-[22.5rem]">
            <div className="flex max-w-full flex-col gap-3 rounded-3xl border border-border/50 bg-card/70 p-4 shadow-sm ring-1 ring-black/[0.03] backdrop-blur-sm dark:ring-white/[0.06] sm:p-5">
              <MarketSegmentedControl market={state.market} onChange={switchMarket} />

              <Accordion
                type="multiple"
                defaultValue={[]}
                className="max-w-full min-w-0 overflow-visible rounded-2xl border border-border/80 bg-muted/10 shadow-sm dark:bg-muted/5"
              >
              <AccordionItem value="basics" className="border-border/60">
                <AccordionTrigger className="py-3 hover:no-underline sm:ps-5 sm:pe-12">
                  <div className="min-w-0 flex-1 text-start">
                    <div className="font-semibold leading-tight">Основное</div>
                    <div className="mt-1 text-xs font-normal text-muted-foreground">
                      Марка, модель, поколение, поиск
                    </div>
                  </div>
                </AccordionTrigger>
                <AccordionContent className="space-y-3 sm:px-5">
                  {facets ? (
                    <div className="space-y-2">
                      <FacetMultiDropdown
                        label="Марка"
                        rows={facets.marks}
                        selected={new Set(state.marks)}
                        onToggle={(v) => toggle("marks", v)}
                      />
                      <FacetMultiDropdown
                        label="Модель"
                        rows={facets.models}
                        selected={new Set(state.models)}
                        onToggle={(v) => toggle("models", v)}
                        disabled={state.marks.length === 0}
                      />
                      <FacetMultiDropdown
                        label="Поколение"
                        rows={facets.generations}
                        selected={new Set(state.generations)}
                        onToggle={(v) => toggle("generations", v)}
                        disabled={state.models.length === 0}
                      />
                      <FacetMultiDropdown
                        label="Комплектация"
                        rows={facets.trims}
                        selected={new Set(state.trims)}
                        onToggle={(v) => toggle("trims", v)}
                        disabled={state.generations.length === 0}
                      />
                    </div>
                  ) : (
                    <div className="space-y-2">
                      <Skeleton className="h-9 w-full rounded-2xl" />
                      <Skeleton className="h-9 w-full rounded-2xl" />
                      <Skeleton className="h-9 w-full rounded-2xl" />
                      <Skeleton className="h-9 w-full rounded-2xl" />
                    </div>
                  )}
                  <div>
                    <Label className="text-xs font-medium text-muted-foreground">Поиск в каталоге</Label>
                    <div className="mt-2 flex min-w-0 flex-col gap-2 sm:flex-row sm:items-stretch">
                      <Input
                        value={qDraft}
                        onChange={(e) => setQDraft(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === "Enter") {
                            navigate({ ...state, q: qDraft.trim(), page: 1 });
                          }
                        }}
                        placeholder="Марка, модель…"
                        className="min-h-9 min-w-0 flex-1"
                      />
                      <Button
                        type="button"
                        size="sm"
                        className="h-9 w-full shrink-0 sm:w-auto"
                        onClick={() => navigate({ ...state, q: qDraft.trim(), page: 1 })}
                      >
                        Найти
                      </Button>
                    </div>
                  </div>
                  <div>
                    <Label className="text-xs font-medium text-muted-foreground">Сортировка</Label>
                    <SortDropdown
                      value={state.sort}
                      onChange={(sort) => navigate({ ...state, sort, page: 1 })}
                    />
                  </div>
                </AccordionContent>
              </AccordionItem>

              <AccordionItem value="tech" className="border-border/60">
                <AccordionTrigger className="py-3 hover:no-underline sm:ps-5 sm:pe-12">
                  <div className="min-w-0 flex-1 text-start">
                    <div className="font-semibold leading-tight">Техника и кузов</div>
                    <div className="mt-1 text-xs font-normal text-muted-foreground">
                      Тип кузова, топливо, привод, КПП
                    </div>
                  </div>
                </AccordionTrigger>
                <AccordionContent className="space-y-3 sm:px-5">
                  <label className="flex min-w-0 cursor-pointer items-start gap-2 rounded-xl border border-border bg-muted/20 px-3 py-2.5 text-sm leading-snug shadow-sm [overflow-wrap:anywhere]">
                    <Checkbox
                      checked={state.drive_awd}
                      onCheckedChange={(v) =>
                        navigate({ ...state, drive_awd: Boolean(v), page: 1 })
                      }
                      className="shrink-0"
                    />
                    Только полный привод (AWD)
                  </label>
                  <label className="flex min-w-0 cursor-pointer items-start gap-2 rounded-xl border border-border bg-muted/20 px-3 py-2.5 text-sm leading-snug shadow-sm [overflow-wrap:anywhere]">
                    <Checkbox
                      checked={state.power_hp_le_160}
                      onCheckedChange={(v) =>
                        navigate({ ...state, power_hp_le_160: Boolean(v), page: 1 })
                      }
                      className="shrink-0"
                    />
                    Только авто до 160 л.с.
                  </label>
                  {facets ? (
                    <div className="space-y-2">
                      <FacetMultiDropdown
                        label="Кузов"
                        rows={facets.bodies}
                        selected={new Set(state.body)}
                        onToggle={(v) => toggle("body", v)}
                      />
                      <FacetMultiDropdown
                        label="Топливо"
                        rows={facets.fuels}
                        selected={new Set(state.fuel)}
                        onToggle={(v) => toggle("fuel", v)}
                      />
                      <FacetMultiDropdown
                        label="КПП"
                        rows={facets.transmissions}
                        selected={new Set(state.trans)}
                        onToggle={(v) => toggle("trans", v)}
                      />
                    </div>
                  ) : (
                    <div className="space-y-2">
                      <Skeleton className="h-10 w-full rounded-2xl" />
                      <Skeleton className="h-10 w-full rounded-2xl" />
                      <Skeleton className="h-10 w-full rounded-2xl" />
                    </div>
                  )}
                </AccordionContent>
              </AccordionItem>

              <AccordionItem value="price" className="border-border/60">
                <AccordionTrigger className="py-3 hover:no-underline sm:ps-5 sm:pe-12">
                  <div className="min-w-0 flex-1 text-start">
                    <div className="font-semibold leading-tight">Цена, пробег и год</div>
                    <div className="mt-1 text-xs font-normal text-muted-foreground">
                      Диапазоны в рублях, км и год выпуска
                    </div>
                  </div>
                </AccordionTrigger>
                <AccordionContent className="sm:px-5">
                  <RangeBlock state={state} navigate={navigate} />
                </AccordionContent>
              </AccordionItem>

              <AccordionItem value="look" className="border-border/60 border-b-0">
                <AccordionTrigger className="py-3 hover:no-underline sm:ps-5 sm:pe-12">
                  <div className="min-w-0 flex-1 text-start">
                    <div className="font-semibold leading-tight">Внешний вид</div>
                    <div className="mt-1 text-xs font-normal text-muted-foreground">Цвет кузова</div>
                  </div>
                </AccordionTrigger>
                <AccordionContent className="space-y-3 sm:px-5">
                  {facets ? (
                    <>
                      <div className="rounded-xl border border-border bg-muted/20 p-3">
                        <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                          Популярные цвета
                        </p>
                        <div className="mt-2 flex flex-wrap gap-2">
                          {facets.colors.slice(0, 8).map((row) => {
                            const active = state.color.includes(row.value);
                            return (
                              <Button
                                key={row.value}
                                type="button"
                                variant={active ? "default" : "secondary"}
                                size="xs"
                                className="h-8 max-w-full rounded-full px-2.5"
                                onClick={() => toggle("color", row.value)}
                              >
                                <span
                                  className={cn(
                                    "size-3 shrink-0 rounded-full",
                                    colorSwatchClass(facetRowLabel(row)),
                                  )}
                                  aria-hidden
                                />
                                <span className="truncate">{facetRowLabel(row)}</span>
                              </Button>
                            );
                          })}
                        </div>
                      </div>
                      <FacetMultiDropdown
                        label="Все цвета"
                        rows={facets.colors}
                        selected={new Set(state.color)}
                        onToggle={(v) => toggle("color", v)}
                      />
                    </>
                  ) : (
                    <div className="space-y-2">
                      <Skeleton className="h-20 w-full rounded-xl" />
                      <Skeleton className="h-10 w-full rounded-2xl" />
                    </div>
                  )}
                </AccordionContent>
              </AccordionItem>
            </Accordion>

            <Button type="button" variant="outline" className="w-full shrink-0" onClick={reset}>
              Сбросить фильтры
            </Button>
          </div>
        </aside>

        <div className="min-w-0 flex-1">
          <div className="mb-5 rounded-3xl border border-border/50 bg-card/70 p-4 shadow-sm ring-1 ring-black/[0.03] dark:ring-white/[0.06] sm:mb-6 sm:p-5">
            <h1 className="text-base font-semibold leading-snug tracking-tight [overflow-wrap:anywhere] sm:text-lg md:text-xl">
              {title}
            </h1>
            <div className="mt-2 flex min-w-0 flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-center sm:gap-x-3 sm:gap-y-2">
              <p className="min-w-0 text-sm leading-snug text-muted-foreground [overflow-wrap:anywhere]">
                Автомобилей в каталоге:{" "}
                <span className="font-medium text-foreground">
                  {search.meta.total.toLocaleString("ru-RU")}
                </span>
                {loading ? " · обновление…" : ""}
              </p>
              {dailyNewLoading ? (
                <Skeleton className="h-7 w-full max-w-md rounded-full sm:w-[min(100%,20rem)]" />
              ) : dailyNewCount !== null ? (
                <span
                  className="inline-flex max-w-full items-start gap-1.5 rounded-full border border-white/20 bg-black/50 px-3 py-1.5 text-xs font-medium leading-snug text-white shadow-sm [overflow-wrap:anywhere] sm:items-center"
                  title="Записи, впервые добавленные в каталог сегодня. Сутки по часовому поясу Екатеринбурга — как расписание ночных обновлений."
                >
                  <Sparkles
                    className={cn(
                      "mt-0.5 size-3.5 shrink-0 opacity-85 text-white sm:mt-0",
                    )}
                    aria-hidden
                  />
                  {carsAddedTodayLabel(dailyNewCount)}
                </span>
              ) : null}
            </div>
            {activeChips.length ? (
              <motion.div
                className="mt-4 flex min-w-0 flex-wrap items-stretch gap-2"
                layout
                transition={{ duration: 0.2, ease: "easeOut" }}
              >
                <AnimatePresence initial={false}>
                  {activeChips.map((chip, idx) => (
                    <motion.div
                      key={`${chip.key}-${chip.value ?? idx}`}
                      layout
                      initial={{ opacity: 0, scale: 0.94 }}
                      animate={{ opacity: 1, scale: 1 }}
                      exit={{ opacity: 0, scale: 0.94 }}
                      transition={{ duration: 0.16, ease: "easeOut" }}
                    >
                      <Button
                        type="button"
                        variant="secondary"
                        size="xs"
                        className="h-auto min-h-7 max-w-full justify-start whitespace-normal rounded-full px-2.5 py-1.5 text-start text-xs font-normal [overflow-wrap:anywhere]"
                        onClick={() => removeChip(chip)}
                        title="Убрать фильтр"
                      >
                        {chip.label} ×
                      </Button>
                    </motion.div>
                  ))}
                </AnimatePresence>
                <Button
                  type="button"
                  size="xs"
                  className="h-auto min-h-7 shrink-0 rounded-full px-3 py-1.5"
                  onClick={reset}
                >
                  Сбросить все
                </Button>
              </motion.div>
            ) : null}
          </div>

          <motion.ul
            className="flex flex-col gap-3"
            variants={cardListVariants}
            initial="hidden"
            animate="show"
            key={key}
          >
            {search.result.map((car, idx) => {
              const preview = previewImageUrls(car);
              const cardData = (car.data ?? {}) as Record<string, unknown>;
              const attrChips = catalogCardAttributeChips(
                cardData,
                car.year_num,
              );
              const passability = carPassabilityStatus(cardData);
              const overlayBadges = cardOverlayBadges(cardData, car.year_num, state.market);
              const listingSold = Boolean(car.encar_listing_sold || car.dongchedi_listing_sold);
              const fav = isFavorite(car.id);
              const showCopied = copiedId === car.id;
              return (
                <motion.li key={car.id} variants={cardItemVariants} layout>
                  <Card
                    size="sm"
                    className="flex flex-col items-stretch gap-0 overflow-hidden !py-0 data-[size=sm]:!py-0 shadow-sm ring-1 ring-border/70 transition-shadow hover:shadow-md sm:min-h-[13rem] sm:flex-row"
                  >
                    <Link
                      href={`/car/${encodeURIComponent(car.id)}`}
                      prefetch
                      className="relative h-52 w-full shrink-0 overflow-hidden rounded-t-2xl bg-muted/30 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-inset sm:h-auto sm:w-60 sm:self-stretch sm:rounded-s-2xl sm:rounded-tr-none md:w-72"
                    >
                      <div className="relative size-full">
                        <CatalogCardImage
                          images={preview}
                          alt={car.title || car.id}
                          eager={idx < 4}
                          sold={listingSold}
                        />
                        <div className="pointer-events-none absolute inset-x-0 bottom-0 flex items-end justify-between gap-2 bg-gradient-to-t from-black/50 via-black/20 to-transparent px-2 pb-2 pt-14">
                          <div className="flex flex-wrap items-center gap-1">
                            {overlayBadges.length ? (
                              overlayBadges.map((b, i) => (
                                <Badge
                                  key={`${car.id}-ob-${i}`}
                                  variant={i === 0 ? "secondary" : "outline"}
                                  className="max-w-[10rem] truncate rounded-md border border-white/20 bg-background/95 px-1.5 py-0 text-[10px] font-medium shadow-sm sm:max-w-[12rem] sm:text-[11px]"
                                  title={b}
                                >
                                  {b}
                                </Badge>
                              ))
                            ) : (
                              <Badge
                                variant="secondary"
                                className="rounded-md border border-white/20 bg-background/95 px-1.5 py-0 text-[10px] font-medium shadow-sm sm:text-[11px]"
                              >
                                {car.year_num ? `${car.year_num}` : "—"}
                              </Badge>
                            )}
                            {listingSold ? (
                              <Badge className="rounded-md border border-red-900/30 bg-red-600 px-1.5 py-0 text-[10px] font-semibold uppercase tracking-wide text-white shadow-sm sm:text-xs">
                                Продан
                              </Badge>
                            ) : null}
                          </div>
                          {isCatalogListedToday(car.catalog_created_at) ? (
                            <span
                              className="max-w-[min(100%,10.5rem)] shrink-0 truncate rounded-md bg-black/50 px-2 py-0.5 text-center text-[10px] font-medium leading-tight text-white shadow-md ring-1 ring-white/15 backdrop-blur-[2px] sm:max-w-[12rem] sm:py-1 sm:text-[11px]"
                              title="Впервые попало в каталог за сегодня (по дате сервера, Екатеринбург)"
                            >
                              Добавлено сегодня
                            </span>
                          ) : null}
                        </div>
                      </div>
                    </Link>
                    <div className="flex min-w-0 flex-1 flex-col justify-between gap-0 sm:rounded-e-2xl">
                      <div className="flex items-start justify-between gap-3 border-b border-border/50 px-3 py-3 sm:px-4 md:px-5">
                        <Link
                          href={`/car/${encodeURIComponent(car.id)}`}
                          prefetch
                          className="min-w-0 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                        >
                          <p className="font-heading line-clamp-2 text-[15px] font-semibold leading-snug sm:text-base">
                            {car.title || car.id}
                          </p>
                        </Link>
                        <div className="flex shrink-0 items-center gap-1.5">
                          <Button
                            type="button"
                            variant="secondary"
                            size="icon-sm"
                            className="rounded-lg shadow-sm"
                            title={showCopied ? "Скопировано" : "Копировать ссылку на объявление"}
                            aria-label="Копировать ссылку"
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
                              <Check className="size-4 text-green-600 dark:text-green-400" />
                            ) : (
                              <Copy className="size-4" />
                            )}
                          </Button>
                          <Button
                            type="button"
                            variant={fav ? "default" : "secondary"}
                            size="icon-sm"
                            className="rounded-lg shadow-sm"
                            title={fav ? "Убрать из избранного" : "В избранное"}
                            aria-pressed={fav}
                            aria-label={fav ? "Убрать из избранного" : "Добавить в избранное"}
                            onClick={() => toggleFavorite(car)}
                          >
                            <Heart className={cn("size-4", fav ? "fill-current" : "")} />
                          </Button>
                        </div>
                      </div>
                      <div className="flex items-start px-3 py-3 sm:px-4 md:px-5">
                        {attrChips.length ? (
                          <ul
                            className="flex min-w-0 flex-wrap justify-start gap-2"
                            aria-label="Краткие характеристики"
                          >
                            {attrChips.map((c) => {
                              const Icon = c.Icon;
                              return (
                                <li key={c.key} className="min-w-0 max-w-full">
                                  <Badge
                                    variant="outline"
                                    className="inline-flex h-auto max-w-full items-center gap-1 rounded-xl border-border/70 bg-muted/25 px-2 py-1 text-[11px] font-medium normal-case text-foreground shadow-sm [overflow-wrap:anywhere] dark:bg-muted/20"
                                  >
                                    <Icon className="size-3 shrink-0 opacity-80" aria-hidden />
                                    <span className="min-w-0">{c.label}</span>
                                  </Badge>
                                </li>
                              );
                            })}
                          </ul>
                        ) : null}
                      </div>
                      <div className="border-t border-border/50 px-3 py-2.5 sm:px-4 md:px-5">
                        <div className="flex flex-wrap items-center gap-2">
                          <Badge
                            variant="secondary"
                            className="inline-flex w-fit max-w-full rounded-lg border border-border/60 bg-muted/90 px-2.5 py-1 text-[15px] font-semibold tabular-nums tracking-tight text-foreground shadow-sm [overflow-wrap:anywhere] dark:bg-muted/50"
                          >
                            {formatCatalogCardPrice(car.price, car.price_on_request)}
                          </Badge>
                          {passability === "passable" ? (
                            <Badge
                              variant="outline"
                              className="inline-flex items-center gap-1 rounded-lg border-emerald-600/40 bg-emerald-600/10 px-2 py-1 text-[11px] font-medium text-emerald-800 dark:text-emerald-200"
                            >
                              Проходной
                              <Tooltip>
                                <TooltipTrigger asChild>
                                  <button
                                    type="button"
                                    className="inline-flex shrink-0"
                                    aria-label="Пояснение для проходного автомобиля"
                                  >
                                    <CircleHelp className="size-3.5" />
                                  </button>
                                </TooltipTrigger>
                                <TooltipContent side="top">
                                  «Проходной автомобиль»: на него действуют льготные таможенные
                                  тарифы.
                                </TooltipContent>
                              </Tooltip>
                            </Badge>
                          ) : passability === "young" ? (
                            <Badge
                              variant="outline"
                              className="inline-flex items-center gap-1 rounded-lg border-red-600/40 bg-red-600/10 px-2 py-1 text-[11px] font-medium text-red-800 dark:text-red-200"
                            >
                              Высокая ставка
                              <Tooltip>
                                <TooltipTrigger asChild>
                                  <button
                                    type="button"
                                    className="inline-flex shrink-0"
                                    aria-label="Пояснение для автомобиля менее 3 лет"
                                  >
                                    <CircleHelp className="size-3.5" />
                                  </button>
                                </TooltipTrigger>
                                <TooltipContent side="top">
                                  Автомобиль менее 3 лет: на него действуют повышенные таможенные
                                  тарифы.
                                </TooltipContent>
                              </Tooltip>
                            </Badge>
                          ) : passability === "old" ? (
                            <Badge
                              variant="outline"
                              className="inline-flex items-center gap-1 rounded-lg border-red-600/40 bg-red-600/10 px-2 py-1 text-[11px] font-medium text-red-800 dark:text-red-200"
                            >
                              Высокая ставка
                              <Tooltip>
                                <TooltipTrigger asChild>
                                  <button
                                    type="button"
                                    className="inline-flex shrink-0"
                                    aria-label="Пояснение для автомобиля старше 5 лет"
                                  >
                                    <CircleHelp className="size-3.5" />
                                  </button>
                                </TooltipTrigger>
                                <TooltipContent side="top">
                                  Автомобиль старше 5 лет: на него действуют повышенные таможенные
                                  тарифы.
                                </TooltipContent>
                              </Tooltip>
                            </Badge>
                          ) : null}
                        </div>
                      </div>
                    </div>
                  </Card>
                </motion.li>
              );
            })}
            {loading && search.result.length === 0
              ? Array.from({ length: PER_PAGE }).map((_, i) => <ListRowSkeleton key={`sk-${i}`} />)
              : null}
          </motion.ul>

          {search.result.length === 0 && !loading ? (
            <p className="mt-16 text-center text-muted-foreground">Ничего не найдено по текущим фильтрам.</p>
          ) : null}

          <Pagination className="mt-10">
            <PaginationContent className="flex-wrap justify-center gap-1">
              <PaginationItem>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="gap-1 rounded-full ps-2"
                  disabled={state.page <= 1}
                  onClick={() => navigate({ ...state, page: state.page - 1 })}
                >
                  <ChevronLeft className="size-4 rtl:rotate-180" />
                  <span className="hidden sm:inline">Назад</span>
                </Button>
              </PaginationItem>
              {pageItems.map((item, idx) =>
                item === "ellipsis" ? (
                  <PaginationItem key={`ellipsis-${idx}`}>
                    <PaginationEllipsis />
                  </PaginationItem>
                ) : (
                  <PaginationItem key={item}>
                    <Button
                      type="button"
                      variant={state.page === item ? "outline" : "ghost"}
                      size="sm"
                      className="min-w-9 rounded-full tabular-nums"
                      onClick={() => navigate({ ...state, page: item })}
                      aria-current={state.page === item ? "page" : undefined}
                    >
                      {item}
                    </Button>
                  </PaginationItem>
                ),
              )}
              <PaginationItem>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="gap-1 rounded-full pe-2"
                  disabled={!search.meta.next_cursor}
                  onClick={() => navigate({ ...state, page: state.page + 1 })}
                >
                  <span className="hidden sm:inline">Вперёд</span>
                  <ChevronRight className="size-4 rtl:rotate-180" />
                </Button>
              </PaginationItem>
            </PaginationContent>
          </Pagination>
        </div>
      </div>
      </div>
    </div>
  );
}
