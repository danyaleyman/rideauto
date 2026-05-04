"use client";

import Link from "next/link";
import dynamic from "next/dynamic";
import { useRouter, useSearchParams } from "next/navigation";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import {
  Fragment,
  Suspense,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { catalogBreadcrumbSegments } from "@/lib/catalog-breadcrumbs";
import {
  cardOverlayBadges,
  carPassabilityStatus,
  carsAddedTodayLabel,
  catalogCardAttributeChips,
  catalogSearchErrorHint,
  colorSwatchClass,
  facetRowLabel,
  groupFacetRows,
  previewImageUrls,
  shouldShowPendingNavigation,
  visiblePageItems,
} from "@/lib/catalog-client-utils";
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
import { getCarPageAbsoluteUrl } from "@/lib/car-url";
import { isCatalogListedToday } from "@/lib/catalog-listed-today";
import { isCatalogDiagEnabled, sendCatalogDiagEvent } from "@/lib/catalog-diagnostics";
import { dedupeSlimCarsByVin } from "@/lib/catalog-vin-dedupe";
import {
  buildNormalizedCarTitle,
  fuelSortRank,
  normalizeCatalogDisplayLabel,
  normalizeFuelLabel,
  trimFacetLabelMinusGeneration,
} from "@/lib/car-detail-data";
import { formatCatalogCardPrice } from "@/lib/format-price";
import { LocaleSwitchLinks } from "@/components/LocaleSwitchLinks";
import { reportClientError } from "@/lib/observability";
import { useLocaleContext } from "@/components/LocaleProvider";
import { siteBreadcrumbBarClass } from "@/lib/site-layout";
import { useFavorites } from "@/hooks/use-favorites";
import { useAuth } from "@/components/AuthProvider";
import { MarketSegmentedControl } from "@/components/catalog/MarketSegmentedControl";
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
import { ColorFacetDialog, FacetMultiDropdown } from "@/components/catalog/CatalogFilterPrimitives";
import {
  cardItemVariants,
  cardListVariants,
  CatalogCardImage,
  ListRowSkeleton,
  RangeBlock,
  SortDropdown,
} from "@/components/catalog/CatalogBlockWidgets";
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
import { MOTION_PRESETS, MOTION_TOKENS } from "@/components/ui/motion";
import {
  CircleHelp,
  Check,
  ChevronLeft,
  ChevronRight,
  Copy,
  Heart,
  Loader2,
  Sparkles,
} from "lucide-react";
import type { FacetRow, FacetsResponse, SearchResponse } from "@/lib/types";

export function CatalogClient({
  initialSearch,
  ssrKey,
  ssrDegraded = false,
}: {
  initialSearch: SearchResponse;
  ssrKey: string;
  /** SSR не смог получить выдачу — клиент обязан запросить API; показываем подсказку до успешной загрузки. */
  ssrDegraded?: boolean;
}) {
  const reduceMotion = useReducedMotion();
  const router = useRouter();
  const sp = useSearchParams();
  const spStr = sp.toString();
  const diagEnabled = useMemo(() => isCatalogDiagEnabled(spStr), [spStr]);
  const { t } = useLocaleContext();
  const state = useMemo(() => parseCatalogUrl(new URLSearchParams(spStr)), [spStr]);
  const key = useMemo(() => catalogStateKey(state), [state]);

  const [search, setSearch] = useState<SearchResponse>(initialSearch);
  const [facets, setFacets] = useState<FacetsResponse | null>(null);
  const [loading, setLoading] = useState(() => Boolean(ssrDegraded));
  const [err, setErr] = useState<string | null>(null);
  const [refetchTick, setRefetchTick] = useState(0);
  const [online, setOnline] = useState(true);
  const [showSsrDegradedNotice, setShowSsrDegradedNotice] = useState(ssrDegraded);
  const [qDraft, setQDraft] = useState(state.q);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [openingCarId, setOpeningCarId] = useState<string | null>(null);
  const [dailyNewCount, setDailyNewCount] = useState<number | null>(null);
  const [dailyNewLoading, setDailyNewLoading] = useState(true);
  const facetsCacheRef = useRef<Map<string, FacetsResponse>>(new Map());
  const resultsListRef = useRef<HTMLUListElement>(null);
  const prevCatalogPageRef = useRef<number | null>(null);
  const { toggle: toggleFavorite, isFavorite } = useFavorites();
  const { authenticated } = useAuth();

  useEffect(() => {
    setQDraft(state.q);
  }, [state.q]);

  useEffect(() => {
    const onOff = () => setOnline(typeof navigator !== "undefined" ? navigator.onLine : true);
    onOff();
    window.addEventListener("online", onOff);
    window.addEventListener("offline", onOff);
    return () => {
      window.removeEventListener("online", onOff);
      window.removeEventListener("offline", onOff);
    };
  }, []);

  useEffect(() => {
    // Query changed in-place without unmount: clear stale "opening..." marker.
    setOpeningCarId(null);
  }, [key]);

  useEffect(() => {
    if (prevCatalogPageRef.current === null) {
      prevCatalogPageRef.current = state.page;
      return;
    }
    if (prevCatalogPageRef.current !== state.page) {
      prevCatalogPageRef.current = state.page;
      const el = resultsListRef.current;
      if (!el) return;
      if (reduceMotion) el.scrollIntoView({ block: "start" });
      else el.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }, [state.page, reduceMotion]);

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
        // Не дублируем запрос к /api/search при гидрации, если URL совпал с SSR (ssrKey === key).
        const useSsrPayload = !ssrDegraded && key === ssrKey;
        const searchP = useSsrPayload
          ? Promise.resolve(initialSearch)
          : fetchSearchClient(sq, { signal: ac.signal });
        const sRes = await searchP;
        if (ac.signal.aborted) return;
        setSearch(sRes);
        setShowSsrDegradedNotice(false);
        sendCatalogDiagEvent(diagEnabled, "catalog_search_ok", {
          key,
          duration_ms: Date.now() - started,
          total: sRes.meta?.total ?? null,
          result_len: sRes.result?.length ?? null,
        }, { market: state.market });
      } catch (e) {
        if (ac.signal.aborted) return;
        setErr(e instanceof Error ? e.message : "Ошибка загрузки");
        reportClientError(e, { area: "catalog_search", key, page: state.page });
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
  }, [diagEnabled, key, refetchTick, ssrDegraded, ssrKey, state, initialSearch]);

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
      next.clusters = [];
      next.models = [];
      next.generations = [];
      next.trims = [];
    } else if (field === "clusters") {
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
      clusters: [],
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
      pricing_tier: "",
      customs_included_only: false,
      power_hp_le_160: false,
      drive_awd: false,
      no_accidents_only: false,
      new_only: false,
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
      clusters: [],
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
      pricing_tier: "",
      customs_included_only: false,
      power_hp_le_160: false,
      drive_awd: false,
      no_accidents_only: false,
      new_only: false,
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

  /** Один автомобиль может иметь несколько объявлений с разными id — склеиваем по VIN на текущей странице выдачи. */
  const catalogCarsDisplay = useMemo(() => dedupeSlimCarsByVin(search.result), [search.result]);

  const facetLabelByValue = useMemo(() => {
    const f = facets ?? {
      marks: [],
      clusters: [],
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
      ...(f.clusters ?? []),
      ...f.models,
      ...f.generations,
      ...f.trims,
      ...f.bodies,
      ...f.fuels,
      ...f.transmissions,
      ...f.colors,
    ];
    for (const row of allRows) {
      const label = row.value && f.fuels.some((x) => x.value === row.value) ? normalizeFuelLabel(facetRowLabel(row)) ?? facetRowLabel(row) : facetRowLabel(row);
      map.set(row.value, label);
    }
    return map;
  }, [facets]);

  /** Топ по счётчику фасета — компактный ряд в фильтре, остальное в диалоге. */
  const popularColorRows = useMemo(() => {
    const colorFacets = facets?.colors;
    if (!colorFacets?.length) return [];
    const grouped = groupFacetRows(colorFacets);
    return [...grouped].sort((a, b) => b.count - a.count).slice(0, 4);
  }, [facets?.colors]);

  const trimFacetLabelFormatter = useCallback(
    (row: FacetRow) => {
      const base = facetRowLabel(row);
      if (state.generations.length !== 1) return base;
      const genVal = state.generations[0];
      const genLbl =
        facetLabelByValue.get(genVal) ??
        normalizeCatalogDisplayLabel(genVal) ??
        genVal;
      return trimFacetLabelMinusGeneration(base, genLbl);
    },
    [state.generations, facetLabelByValue],
  );

  const activeChips = useMemo(() => {
    const withLabel = (v: string, key?: keyof CatalogUrlState) =>
      key === "fuel" ? normalizeFuelLabel(facetLabelByValue.get(v) ?? v) ?? (facetLabelByValue.get(v) ?? v) : facetLabelByValue.get(v) ?? v;
    const chips: Array<{ key: keyof CatalogUrlState; label: string; value?: string }> = [];
    const pushDedupByLabel = (key: keyof CatalogUrlState, prefix: string, values: string[]) => {
      const seen = new Set<string>();
      for (const raw of values) {
        const shown = withLabel(raw, key);
        const marker = shown.toLowerCase();
        if (seen.has(marker)) continue;
        seen.add(marker);
        chips.push({ key, label: `${prefix}: ${shown}`, value: raw });
      }
    };
    pushDedupByLabel("marks", "Марка", state.marks);
    pushDedupByLabel("clusters", "Линейка", state.clusters);
    pushDedupByLabel("models", "Модель", state.models);
    pushDedupByLabel("generations", "Поколение", state.generations);
    pushDedupByLabel("trims", "Комплектация", state.trims);
    state.body.forEach((v) => chips.push({ key: "body", label: `Кузов: ${withLabel(v)}`, value: v }));
    state.fuel.forEach((v) => chips.push({ key: "fuel", label: `Топливо: ${withLabel(v, "fuel")}`, value: v }));
    state.trans.forEach((v) => chips.push({ key: "trans", label: `КПП: ${withLabel(v)}`, value: v }));
    state.color.forEach((v) => chips.push({ key: "color", label: `Цвет: ${withLabel(v)}`, value: v }));
    if (state.drive_awd) chips.push({ key: "drive_awd", label: "Полный привод" });
    if (state.power_hp_le_160) chips.push({ key: "power_hp_le_160", label: "До 160 л.с." });
    if (state.passable_only) chips.push({ key: "passable_only", label: "Только проходные авто" });
    if (state.pricing_tier === "full_customs") {
      chips.push({ key: "pricing_tier", label: "Оценка: под ключ с таможней РФ" });
    } else if (state.pricing_tier === "korea_land_only") {
      chips.push({ key: "pricing_tier", label: "Оценка: без таможни РФ" });
    } else if (state.pricing_tier === "price_on_request") {
      chips.push({ key: "pricing_tier", label: "Оценка: цена по запросу" });
    }
    if (state.customs_included_only && state.pricing_tier !== "full_customs") {
      chips.push({ key: "customs_included_only", label: "В цене учтена таможня РФ" });
    }
    if (state.no_accidents_only) chips.push({ key: "no_accidents_only", label: "Только без ДТП" });
    if (state.new_only) chips.push({ key: "new_only", label: "Только новые авто (< 500 км)" });
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

  const breadcrumbSegments = useMemo(
    () => catalogBreadcrumbSegments(state, facetLabelByValue),
    [state, facetLabelByValue],
  );

  const removeChip = (chip: { key: keyof CatalogUrlState; value?: string }) => {
    if (
      chip.key === "marks" ||
      chip.key === "clusters" ||
      chip.key === "models" ||
      chip.key === "generations" ||
      chip.key === "trims" ||
      chip.key === "body" ||
      chip.key === "fuel" ||
      chip.key === "trans" ||
      chip.key === "color"
    ) {
      if (!chip.value) return;
      const targetLabel =
        chip.key === "fuel"
          ? normalizeFuelLabel(facetLabelByValue.get(chip.value) ?? chip.value) ?? (facetLabelByValue.get(chip.value) ?? chip.value)
          : facetLabelByValue.get(chip.value) ?? chip.value;
      const cur = state[chip.key];
      if (!Array.isArray(cur)) return;
      const toRemove = cur.filter((v) => {
        const shown =
          chip.key === "fuel"
            ? normalizeFuelLabel(facetLabelByValue.get(v) ?? v) ?? (facetLabelByValue.get(v) ?? v)
            : facetLabelByValue.get(v) ?? v;
        return shown === targetLabel;
      });
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
    if (chip.key === "pricing_tier") {
      navigate({ ...state, pricing_tier: "", page: 1 });
      return;
    }
    if (chip.key === "customs_included_only") {
      navigate({ ...state, customs_included_only: false, page: 1 });
      return;
    }
    if (chip.key === "no_accidents_only") {
      navigate({ ...state, no_accidents_only: false, page: 1 });
      return;
    }
    if (chip.key === "new_only") {
      navigate({ ...state, new_only: false, page: 1 });
      return;
    }
    navigate({ ...state, [chip.key]: "", page: 1 });
  };

  return (
    <>
        <div className={siteBreadcrumbBarClass}>
          <Breadcrumb className="min-w-0 flex-1">
            <BreadcrumbList className="flex-wrap gap-x-1 gap-y-1 sm:flex-nowrap">
              {breadcrumbSegments.map((seg, i) => {
                const last = i === breadcrumbSegments.length - 1;
                return (
                  <Fragment key={`${i}-${seg.label}`}>
                    {i > 0 ? <BreadcrumbSeparator /> : null}
                    <BreadcrumbItem className={last ? "min-w-0 max-w-full" : undefined}>
                      {last ? (
                        <BreadcrumbPage className="line-clamp-2 break-words text-start font-medium [overflow-wrap:anywhere] sm:line-clamp-1">
                          {seg.label}
                        </BreadcrumbPage>
                      ) : seg.href ? (
                        <BreadcrumbLink asChild>
                          <Link href={seg.href}>{seg.label}</Link>
                        </BreadcrumbLink>
                      ) : (
                        <BreadcrumbPage>{seg.label}</BreadcrumbPage>
                      )}
                    </BreadcrumbItem>
                  </Fragment>
                );
              })}
            </BreadcrumbList>
          </Breadcrumb>
        </div>

        {!online ? (
          <div
            className="mb-4 rounded-xl border border-amber-600/35 bg-amber-500/10 px-4 py-3 text-sm text-amber-950 [overflow-wrap:anywhere] dark:text-amber-50"
            role="alert"
          >
            <p className="font-medium">{t("catalog.offline.title")}</p>
            <p className="mt-1 text-amber-900/90 dark:text-amber-100/90">{t("catalog.offline.hint")}</p>
          </div>
        ) : null}

        {showSsrDegradedNotice ? (
          <div
            className="mb-4 rounded-xl border border-amber-500/35 bg-amber-500/10 px-4 py-3 text-sm text-amber-950 [overflow-wrap:anywhere] dark:text-amber-50"
            role="status"
          >
            Не удалось получить каталог при отрисовке на сервере — загружаем выдачу в браузере. Проверьте логи API и
            переменную <code className="break-all rounded bg-background/80 px-1 dark:bg-background/40">WRA_API_INTERNAL</code> в
            контейнере <code className="rounded bg-background/80 px-1 dark:bg-background/40">web</code>. Для клиента по
            умолчанию используются запросы на тот же сайт (<code className="rounded bg-background/80 px-1">/api/…</code>); не
            задавайте <code className="rounded bg-background/80 px-1">NEXT_PUBLIC_API_BASE=http://127.0.0.1:8080</code>, если
            открываете сайт не с localhost.
          </div>
        ) : null}

        {err ? (
          <div className="mb-4 rounded-xl border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm [overflow-wrap:anywhere]">
            <p className="font-medium text-destructive">Не удалось загрузить каталог</p>
            <p className="mt-1 text-destructive/90">{err}</p>
            {catalogSearchErrorHint(err) ? (
              <p className="mt-2 text-muted-foreground">{catalogSearchErrorHint(err)}</p>
            ) : null}
            <p className="mt-2 text-xs text-muted-foreground">
              Убедитесь, что API отвечает (логи сервиса <code className="rounded bg-background/80 px-1">api</code>). В Docker не
              используйте для браузера <code className="rounded bg-background/80 px-1">127.0.0.1:8080</code>, если заходите по IP
              или домену — оставьте <code className="rounded bg-background/80 px-1">NEXT_PUBLIC_API_BASE</code> пустым или
              укажите публичный URL с тем же host, что и сайт.
            </p>
            <Button
              type="button"
              variant="secondary"
              size="sm"
              className="mt-3 rounded-full"
              onClick={() => {
                setErr(null);
                setRefetchTick((t) => t + 1);
              }}
            >
              Повторить запрос
            </Button>
          </div>
        ) : null}

        <div className="flex min-w-0 flex-col gap-6 lg:flex-row lg:items-start lg:gap-7">
          <aside className="w-full min-w-0 shrink-0 self-start lg:w-[22.5rem]">
            <div className="flex max-w-full flex-col gap-3 rounded-3xl border border-border/50 bg-card/70 p-4 shadow-sm ring-1 ring-elevated-ring backdrop-blur-sm sm:p-5">
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
                      Марка, линейка, модель, поколение, поиск
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
                        label="Линейка"
                        rows={facets.clusters ?? []}
                        selected={new Set(state.clusters)}
                        onToggle={(v) => toggle("clusters", v)}
                        disabled={state.marks.length === 0}
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
                        labelFormatter={trimFacetLabelFormatter}
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
                  <label className="flex min-w-0 cursor-pointer items-start gap-2 rounded-xl border border-border bg-muted/20 px-3 py-2.5 text-sm leading-snug shadow-sm [overflow-wrap:anywhere]">
                    <Checkbox
                      checked={state.no_accidents_only}
                      onCheckedChange={(v) =>
                        navigate({ ...state, no_accidents_only: Boolean(v), page: 1 })
                      }
                      className="shrink-0"
                    />
                    Только без ДТП
                  </label>
                  <label className="flex min-w-0 cursor-pointer items-start gap-2 rounded-xl border border-border bg-muted/20 px-3 py-2.5 text-sm leading-snug shadow-sm [overflow-wrap:anywhere]">
                    <Checkbox
                      checked={state.new_only}
                      onCheckedChange={(v) =>
                        navigate({ ...state, new_only: Boolean(v), page: 1 })
                      }
                      className="shrink-0"
                    />
                    Только новые авто (до 500 км)
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
                        labelFormatter={(row) => normalizeFuelLabel(facetRowLabel(row)) ?? facetRowLabel(row)}
                        comparator={(a, b) => {
                          const ra = fuelSortRank(a);
                          const rb = fuelSortRank(b);
                          if (ra !== rb) return ra - rb;
                          return a.localeCompare(b);
                        }}
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
                  <RangeBlock state={state} navigate={navigate} market={state.market} />
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
                      <div className="rounded-xl border border-border/70 bg-muted/15 p-3 dark:bg-muted/10">
                        <p className="text-xs font-medium text-muted-foreground">Популярные цвета</p>
                        <div className="mt-2 flex flex-wrap gap-2">
                          {popularColorRows.map((row) => {
                            const vals = row.values.length ? row.values : [];
                            const active = vals.some((v) => state.color.includes(v));
                            return (
                              <Button
                                key={row.label}
                                type="button"
                                variant={active ? "default" : "outline"}
                                size="xs"
                                className="h-8 max-w-[calc(50%-0.25rem)] flex-1 basis-[40%] rounded-full border-border/80 px-2.5 text-xs font-medium shadow-sm sm:max-w-none sm:flex-none sm:basis-auto"
                                onClick={() => toggle("color", vals)}
                              >
                                <span
                                  className={cn(
                                    "size-3 shrink-0 rounded-full",
                                    colorSwatchClass(row.label),
                                  )}
                                  aria-hidden
                                />
                                <span className="truncate">{row.label}</span>
                              </Button>
                            );
                          })}
                        </div>
                      </div>
                      <ColorFacetDialog
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
          <div className="mb-5 rounded-3xl border border-border/50 bg-card/70 p-4 shadow-sm ring-1 ring-elevated-ring sm:mb-6 sm:p-5">
            <h1 className="text-base font-semibold leading-snug tracking-tight [overflow-wrap:anywhere] sm:text-lg md:text-xl">
              {title}
            </h1>
            <p className="sr-only" aria-live="polite" aria-atomic="true">
              {err
                ? `Ошибка загрузки: ${err}`
                : loading
                  ? "Загрузка результатов каталога."
                  : `Найдено ${(search.meta?.total ?? 0).toLocaleString("ru-RU")} объявлений. На странице показано ${catalogCarsDisplay.length}. Страница ${state.page}.`}
            </p>
            <div className="mt-2 flex min-w-0 flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-center sm:gap-x-3 sm:gap-y-2">
              <p className="min-w-0 text-sm leading-snug text-muted-foreground [overflow-wrap:anywhere]">
                Автомобилей в каталоге:{" "}
                <span className="font-medium text-foreground">
                  {search.meta.total.toLocaleString("ru-RU")}
                </span>
                {loading ? " · обновление…" : ""}
              </p>
              {openingCarId ? (
                <span className="inline-flex items-center gap-1.5 text-xs text-muted-foreground">
                  <Loader2 className="size-3.5 animate-spin" aria-hidden />
                  Открываем карточку автомобиля…
                </span>
              ) : null}
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
              <Suspense fallback={null}>
                <LocaleSwitchLinks className="shrink-0 text-xs text-muted-foreground" />
              </Suspense>
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
                      initial={MOTION_PRESETS.popInInitial}
                      animate={MOTION_PRESETS.popInAnimate}
                      exit={MOTION_PRESETS.popInExit}
                      transition={{ duration: MOTION_TOKENS.duration.fast, ease: "easeOut" }}
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
            ref={resultsListRef}
            className="flex scroll-mt-28 flex-col gap-3 md:scroll-mt-32"
            variants={reduceMotion ? undefined : cardListVariants}
            initial={reduceMotion ? false : "hidden"}
            animate={reduceMotion ? undefined : "show"}
            key={key}
          >
            {catalogCarsDisplay.map((car, idx) => {
              const preview = previewImageUrls(car);
              const cardData = (car.data ?? {}) as Record<string, unknown>;
              const normalizedTitle =
                buildNormalizedCarTitle(
                  cardData.mark,
                  cardData.model,
                  cardData.generation ?? cardData.configuration,
                  cardData.source,
                ) ||
                normalizeCatalogDisplayLabel(car.title) ||
                car.id;
              const attrChips = catalogCardAttributeChips(
                cardData,
                car.year_num,
              );
              const passability = carPassabilityStatus(cardData);
              const overlayBadges = cardOverlayBadges(cardData, car.year_num, state.market);
              const listingSold = Boolean(car.encar_listing_sold || car.che168_listing_sold);
              const listingReserved = !listingSold && Boolean(car.encar_listing_reserved);
              const listingUnavailable = listingSold || listingReserved;
              const fav = authenticated && isFavorite(car.id);
              const showCopied = copiedId === car.id;
              const openingThisCard = openingCarId === car.id;
              const mobileCommerceStatusSegments: { key: string; label: string; tooltip: string }[] = [];
              if (!listingUnavailable) {
                if (car.pricing_tier === "korea_land_only") {
                  mobileCommerceStatusSegments.push({
                    key: "tier",
                    label: "Без таможни РФ",
                    tooltip:
                      "Указанная сумма — Корея, логистика и сопутствующие сборы по данным каталога; растаможка в РФ в эту цифру не входит и считается отдельно.",
                  });
                }
                if (passability === "passable") {
                  mobileCommerceStatusSegments.push({
                    key: "pass",
                    label: "Проходной",
                    tooltip: "«Проходной автомобиль»: на него действуют льготные таможенные тарифы.",
                  });
                } else if (passability === "young") {
                  mobileCommerceStatusSegments.push({
                    key: "young",
                    label: "Высокая ставка",
                    tooltip: "Автомобиль менее 3 лет: на него действуют повышенные таможенные тарифы.",
                  });
                } else if (passability === "old") {
                  mobileCommerceStatusSegments.push({
                    key: "old",
                    label: "Высокая ставка",
                    tooltip: "Автомобиль старше 5 лет: на него действуют повышенные таможенные тарифы.",
                  });
                }
              }
              const hasListingCommerceBadges = mobileCommerceStatusSegments.length > 0;
              const commerceStatusBadges =
                !listingUnavailable ? (
                  <>
                    {car.pricing_tier === "korea_land_only" ? (
                      <Badge
                        variant="outline"
                        className="inline-flex h-8 max-w-full items-center gap-1 rounded-full border-amber-500/35 bg-amber-500/[0.09] px-2.5 text-[11px] font-medium text-amber-950 [overflow-wrap:anywhere] dark:text-amber-100"
                      >
                        Без таможни РФ
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <button
                              type="button"
                              className="inline-flex shrink-0"
                              aria-label="Пояснение: цена без растаможки РФ"
                            >
                              <CircleHelp className="size-3.5" />
                            </button>
                          </TooltipTrigger>
                          <TooltipContent side="top" className="max-w-[20rem]">
                            Указанная сумма — Корея, логистика и сопутствующие сборы по данным каталога;
                            растаможка в РФ в эту цифру не входит и считается отдельно.
                          </TooltipContent>
                        </Tooltip>
                      </Badge>
                    ) : null}
                    {passability === "passable" ? (
                      <Badge
                        variant="outline"
                        className="inline-flex h-8 items-center gap-1 rounded-full border-emerald-600/35 bg-emerald-600/[0.08] px-2.5 text-[11px] font-medium text-emerald-800 dark:text-emerald-200"
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
                            «Проходной автомобиль»: на него действуют льготные таможенные тарифы.
                          </TooltipContent>
                        </Tooltip>
                      </Badge>
                    ) : passability === "young" ? (
                      <Badge
                        variant="outline"
                        className="inline-flex h-8 items-center gap-1 rounded-full border-red-600/35 bg-red-600/[0.08] px-2.5 text-[11px] font-medium text-red-800 dark:text-red-200"
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
                            Автомобиль менее 3 лет: на него действуют повышенные таможенные тарифы.
                          </TooltipContent>
                        </Tooltip>
                      </Badge>
                    ) : passability === "old" ? (
                      <Badge
                        variant="outline"
                        className="inline-flex h-8 items-center gap-1 rounded-full border-red-600/35 bg-red-600/[0.08] px-2.5 text-[11px] font-medium text-red-800 dark:text-red-200"
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
                            Автомобиль старше 5 лет: на него действуют повышенные таможенные тарифы.
                          </TooltipContent>
                        </Tooltip>
                      </Badge>
                    ) : null}
                  </>
                ) : null;
              const buyTriggerClass =
                "h-8 min-h-8 shrink-0 rounded-full border-primary/25 bg-primary px-3.5 text-xs font-semibold text-primary-foreground shadow-sm hover:bg-primary/92 max-sm:px-4";
              return (
                <motion.li key={car.id} variants={reduceMotion ? undefined : cardItemVariants} layout>
                  <Card
                    size="sm"
                    className="relative flex flex-col items-stretch gap-0 overflow-hidden !py-0 data-[size=sm]:!py-0 shadow-sm ring-1 ring-border/70 transition-shadow hover:shadow-md sm:min-h-[13rem] sm:flex-row"
                  >
                    {openingThisCard ? (
                      <div className="pointer-events-none absolute inset-0 z-20 flex items-center justify-center bg-background/65 backdrop-blur-[1px]">
                        <span className="inline-flex items-center gap-2 rounded-full border border-border/70 bg-background/95 px-3 py-1.5 text-xs font-medium text-foreground shadow-sm">
                          <Loader2 className="size-3.5 animate-spin" aria-hidden />
                          Загрузка карточки…
                        </span>
                      </div>
                    ) : null}
                    <Link
                      href={`/car/${encodeURIComponent(car.id)}`}
                      prefetch
                      className="relative h-52 w-full shrink-0 overflow-hidden rounded-t-2xl bg-muted/30 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-inset sm:h-auto sm:w-60 sm:self-stretch sm:rounded-s-2xl sm:rounded-tr-none md:w-72"
                      onClick={(e) => {
                        if (shouldShowPendingNavigation(e)) setOpeningCarId(car.id);
                      }}
                    >
                      <div className="relative size-full">
                        <CatalogCardImage
                          images={preview}
                          alt={normalizedTitle}
                          eager={idx < 4}
                          sold={listingUnavailable}
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
                            ) : listingReserved ? (
                              <Badge className="rounded-md border border-amber-900/30 bg-amber-500 px-1.5 py-0 text-[10px] font-semibold uppercase tracking-wide text-white shadow-sm sm:text-xs">
                                Зарезервирован
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
                      <div className="flex items-start justify-between gap-2 border-b border-border/50 px-3 py-2.5 sm:gap-3 sm:px-4 sm:py-3.5 md:px-5">
                        <Link
                          href={`/car/${encodeURIComponent(car.id)}`}
                          prefetch
                          className="flex min-w-0 flex-1 items-start focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                          onClick={(e) => {
                            if (shouldShowPendingNavigation(e)) setOpeningCarId(car.id);
                          }}
                        >
                          <p className="font-heading line-clamp-2 min-h-0 text-[15px] font-semibold leading-snug sm:min-h-[2.65rem] sm:text-base md:min-h-[2.85rem]">
                            {normalizedTitle}
                          </p>
                        </Link>
                        <div className="flex shrink-0 items-start gap-1.5 pt-px">
                          <Button
                            type="button"
                            variant="secondary"
                            size="icon-sm"
                            className="rounded-lg shadow-sm"
                            title={showCopied ? "Скопировано" : "Копировать ссылку на объявление"}
                            aria-label={
                              showCopied ? "Ссылка на объявление скопирована" : "Копировать ссылку на объявление"
                            }
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
                          {authenticated ? (
                            <Button
                              type="button"
                              variant={fav ? "default" : "secondary"}
                              size="icon-sm"
                              className="rounded-lg shadow-sm"
                              title={fav ? "Убрать из избранного" : "В избранное"}
                              aria-pressed={fav}
                              aria-label={fav ? "Убрать из избранного" : "Добавить в избранное"}
                              onClick={() => {
                                void toggleFavorite(car);
                              }}
                            >
                              <Heart className={cn("size-4", fav ? "fill-current" : "")} aria-hidden />
                            </Button>
                          ) : null}
                        </div>
                      </div>
                      <div className="flex items-start px-3 pb-1.5 pt-1.5 sm:px-4 sm:pb-2 sm:pt-2.5 md:px-5 md:pt-3 lg:justify-start">
                        {attrChips.length ? (
                          <Link
                            href={`/car/${encodeURIComponent(car.id)}`}
                            prefetch
                            className="min-w-0 flex-1 rounded-lg outline-none focus-visible:ring-2 focus-visible:ring-ring lg:max-w-xl"
                            onClick={(e) => {
                              if (shouldShowPendingNavigation(e)) setOpeningCarId(car.id);
                            }}
                            aria-label={`Открыть объявление: ${normalizedTitle}, краткие характеристики`}
                          >
                            <ul
                              className="flex min-w-0 flex-wrap justify-start gap-1.5 md:gap-2"
                              aria-label="Краткие характеристики"
                            >
                              {attrChips.map((c) => {
                                const Icon = c.Icon;
                                return (
                                  <li key={c.key} className="min-w-0 max-w-full">
                                    <Badge
                                      variant="outline"
                                      className="inline-flex h-auto max-w-full items-center gap-1 rounded-full border-border/55 bg-background/55 px-2.5 py-1 text-[11px] font-medium normal-case text-foreground shadow-none [overflow-wrap:anywhere] max-sm:border-dashed max-sm:text-muted-foreground dark:bg-muted/20"
                                    >
                                      <Icon className="size-3 shrink-0 opacity-80" aria-hidden />
                                      <span className="min-w-0">{c.label}</span>
                                    </Badge>
                                  </li>
                                );
                              })}
                            </ul>
                          </Link>
                        ) : null}
                      </div>
                      <div className="border-t border-border/50 px-3 py-2.5 sm:px-4 md:px-5 max-sm:bg-muted/30 max-sm:dark:bg-muted/20">
                        {!listingUnavailable ? (
                          <>
                            <div className="flex w-full min-w-0 items-start justify-between gap-3 sm:hidden">
                              <div className="min-w-0 flex-1">
                                <Link
                                  href={`/car/${encodeURIComponent(car.id)}`}
                                  prefetch
                                  className="block rounded-md outline-none focus-visible:ring-2 focus-visible:ring-ring"
                                  onClick={(e) => {
                                    if (shouldShowPendingNavigation(e)) setOpeningCarId(car.id);
                                  }}
                                  aria-label={`Открыть объявление: ${normalizedTitle}, цена`}
                                >
                                  <span className="block truncate text-[1.0625rem] font-semibold tabular-nums tracking-tight text-foreground [overflow-wrap:anywhere]">
                                    {formatCatalogCardPrice(car.price, car.price_on_request)}
                                  </span>
                                </Link>
                                {hasListingCommerceBadges ? (
                                  <p className="mt-1 max-w-full text-xs leading-snug text-muted-foreground [overflow-wrap:anywhere]">
                                    {mobileCommerceStatusSegments.map((seg, i) => (
                                      <Fragment key={seg.key}>
                                        {i > 0 ? (
                                          <span className="text-muted-foreground/45" aria-hidden>
                                            {" "}
                                            ·{" "}
                                          </span>
                                        ) : null}
                                        <Tooltip>
                                          <TooltipTrigger asChild>
                                            <button
                                              type="button"
                                              className="inline max-w-full border-b border-dotted border-muted-foreground/45 bg-transparent p-0 text-left font-inherit text-inherit underline-offset-2 hover:border-foreground/35 hover:text-foreground"
                                              aria-label={`Пояснение: ${seg.label}`}
                                            >
                                              {seg.label}
                                            </button>
                                          </TooltipTrigger>
                                          <TooltipContent side="top" className="max-w-[20rem] text-xs">
                                            {seg.tooltip}
                                          </TooltipContent>
                                        </Tooltip>
                                      </Fragment>
                                    ))}
                                  </p>
                                ) : null}
                              </div>
                              <CatalogQuickBuyDialog
                                carId={car.id}
                                carTitle={normalizedTitle}
                                triggerSize="sm"
                                triggerClassName={cn(buyTriggerClass, "mt-0.5 shrink-0")}
                              />
                            </div>
                            <div className="hidden w-full items-center gap-2 sm:flex">
                              <div className="flex min-w-0 flex-wrap items-center gap-2">
                                <Link
                                  href={`/car/${encodeURIComponent(car.id)}`}
                                  prefetch
                                  className="inline-flex max-w-full rounded-lg outline-none focus-visible:ring-2 focus-visible:ring-ring"
                                  onClick={(e) => {
                                    if (shouldShowPendingNavigation(e)) setOpeningCarId(car.id);
                                  }}
                                  aria-label={`Открыть объявление: ${normalizedTitle}, цена`}
                                >
                                  <Badge
                                    variant="secondary"
                                    className="inline-flex h-7 w-fit max-w-full cursor-pointer items-center rounded-lg border border-border/60 bg-muted/90 px-2.5 text-xs font-semibold tabular-nums tracking-tight text-foreground shadow-sm [overflow-wrap:anywhere] dark:bg-muted/50"
                                  >
                                    {formatCatalogCardPrice(car.price, car.price_on_request)}
                                  </Badge>
                                </Link>
                                {commerceStatusBadges}
                              </div>
                              <CatalogQuickBuyDialog
                                carId={car.id}
                                carTitle={normalizedTitle}
                                triggerSize="sm"
                                triggerClassName={cn(buyTriggerClass, "ms-auto")}
                              />
                            </div>
                          </>
                        ) : null}
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
          {catalogCarsDisplay.length < search.result.length ? (
            <p className="mt-2 text-center text-xs text-muted-foreground [overflow-wrap:anywhere]">
              На этой странице не показаны{" "}
              {search.result.length - catalogCarsDisplay.length} дубл. по VIN (разные номера объявлений).
            </p>
          ) : null}

          {search.result.length === 0 && !loading && !err ? (
            <div className="mx-auto mt-16 max-w-md rounded-2xl border border-border/60 bg-card/60 px-6 py-8 text-center shadow-sm ring-1 ring-elevated-ring">
              <p className="text-base font-medium text-foreground">{t("catalog.empty.title")}</p>
              <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{t("catalog.empty.hint")}</p>
              <div className="mt-5 flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:justify-center">
                <Button type="button" className="rounded-full" variant="secondary" onClick={reset}>
                  {t("catalog.empty.reset")}
                </Button>
                <Button type="button" className="rounded-full" variant="outline" asChild>
                  <a href="https://t.me/nikits15" target="_blank" rel="noopener noreferrer">
                    {t("catalog.empty.telegramCta")}
                  </a>
                </Button>
              </div>
            </div>
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
                  aria-label="Предыдущая страница каталога"
                  onClick={() => navigate({ ...state, page: state.page - 1 })}
                >
                  <ChevronLeft className="size-4 rtl:rotate-180" aria-hidden />
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
                      aria-label={`Страница ${item}`}
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
                  aria-label="Следующая страница каталога"
                  onClick={() => navigate({ ...state, page: state.page + 1 })}
                >
                  <span className="hidden sm:inline">Вперёд</span>
                  <ChevronRight className="size-4 rtl:rotate-180" aria-hidden />
                </Button>
              </PaginationItem>
            </PaginationContent>
          </Pagination>
        </div>
      </div>
    </>
  );
}
