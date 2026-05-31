"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useReducedMotion } from "framer-motion";
import { catalogBreadcrumbSegments } from "@/lib/catalog-breadcrumbs";
import { buildCatalogActiveChips, trimFacetLabelFormatter } from "@/lib/catalog-active-chips";
import type { CatalogActiveChip } from "@/lib/catalog-active-chips";
import { facetRowLabel, groupFacetRows, previewImageUrls, visiblePageItems } from "@/lib/catalog-client-utils";
import {
  catalogUrlNeedsCanonicalization,
  canonicalCatalogQueryString,
} from "@/lib/catalog-url-canonical";
import {
  catalogStateKey,
  parseCatalogUrl,
  PER_PAGE,
  stateToBrowserUrl,
  type CatalogUrlState,
} from "@/lib/catalog-url";
import { isCatalogListedToday } from "@/lib/catalog-listed-today";
import { isCatalogDiagEnabled, sendCatalogDiagEvent } from "@/lib/catalog-diagnostics";
import {
  useCatalogDailyAdditionsQuery,
  useCatalogFacetsQuery,
  useCatalogSearchQuery,
} from "@/hooks/use-catalog-queries";
import { useBatchProxiedCatalogThumbUrls } from "@/lib/catalog-image-proxy";
import { dedupeSlimCarsByVin } from "@/lib/catalog-vin-dedupe";
import {
  normalizeCatalogDisplayLabel,
  normalizeFuelLabel,
} from "@/lib/car-detail-data";
import { useLocaleContext } from "@/components/LocaleProvider";
import { buildCatalogSeo } from "@/lib/catalog-seo";
import { displayBodyType, displayColor, displayTransmission } from "@/lib/vehicle-spec-locale";
import { readCatalogDensity, writeCatalogDensity, type CatalogDensity } from "@/lib/catalog-density";
import { useFavorites } from "@/hooks/use-favorites";
import { useAuth } from "@/components/AuthProvider";
import type { SearchResponse } from "@/lib/types";

export type UseCatalogSearchStateArgs = {
  initialSearch: SearchResponse;
  ssrKey: string;
  ssrDegraded?: boolean;
};

export function useCatalogSearchState({
  initialSearch,
  ssrKey,
  ssrDegraded = false,
}: UseCatalogSearchStateArgs) {
  const { locale, t } = useLocaleContext();
  const reduceMotion = useReducedMotion();
  const router = useRouter();
  const sp = useSearchParams();
  const spStr = sp.toString();
  const diagEnabled = useMemo(() => isCatalogDiagEnabled(spStr), [spStr]);
  const state = useMemo(() => parseCatalogUrl(new URLSearchParams(spStr)), [spStr]);
  const key = useMemo(() => catalogStateKey(state), [state]);

  const [online, setOnline] = useState(true);
  const [qDraft, setQDraft] = useState(state.q);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [openingCarId, setOpeningCarId] = useState<string | null>(null);
  const [catalogDensity, setCatalogDensityState] = useState<CatalogDensity>("comfortable");
  const resultsListRef = useRef<HTMLUListElement>(null);
  const prevCatalogPageRef = useRef<number | null>(null);
  const { toggle: toggleFavorite, isFavorite } = useFavorites();
  const { authenticated } = useAuth();

  useEffect(() => {
    setCatalogDensityState(readCatalogDensity());
  }, []);

  const setCatalogDensity = useCallback((next: CatalogDensity) => {
    writeCatalogDensity(next);
    setCatalogDensityState(next);
  }, []);

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
    const sp = new URLSearchParams(spStr);
    if (catalogUrlNeedsCanonicalization(sp)) {
      const qs = canonicalCatalogQueryString(sp);
      router.replace(qs ? `/catalog?${qs}` : "/catalog", { scroll: false });
      return;
    }
    if (!spStr.trim()) {
      const qs = stateToBrowserUrl(parseCatalogUrl(new URLSearchParams()));
      router.replace(qs ? `/catalog?${qs}` : "/catalog", { scroll: false });
    }
  }, [spStr, router]);

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
      sort: "date_new" as const,
    }),
    [state],
  );
  const facetKey = useMemo(() => catalogStateKey(facetState), [facetState]);

  const searchQuery = useCatalogSearchQuery({
    key,
    state,
    initialSearch,
    ssrKey,
    ssrDegraded,
    diagEnabled,
  });
  const facetsQuery = useCatalogFacetsQuery({
    facetKey,
    facetState,
    diagEnabled,
    market: state.market,
  });
  const dailyQuery = useCatalogDailyAdditionsQuery(state.market);

  const search = searchQuery.data ?? initialSearch;
  const facets = facetsQuery.data ?? null;
  const loading =
    searchQuery.isPending || (searchQuery.isFetching && searchQuery.isPlaceholderData);
  const err =
    searchQuery.error == null
      ? null
      : searchQuery.error instanceof Error
        ? searchQuery.error.message
        : t("catalog.error.loadGeneric");
  const showSsrDegradedNotice = ssrDegraded && !searchQuery.isSuccess;
  const dailyNewCount = dailyQuery.data?.count ?? null;
  const dailyNewLoading = dailyQuery.isPending;

  const toggle = useCallback(
    (field: keyof CatalogUrlState, values: string | string[]) => {
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
    },
    [diagEnabled, navigate, state],
  );

  const reset = useCallback(() => {
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
  }, [navigate, state.market]);

  const switchMarket = useCallback(
    (market: CatalogUrlState["market"]) => {
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
    },
    [navigate, state.q, state.sort],
  );

  const title = useMemo(() => buildCatalogSeo(state, locale).title, [state, locale]);

  const pages =
    search.meta.pages > 0 ? search.meta.pages : Math.max(1, Math.ceil(search.meta.total / PER_PAGE));
  const pageItems = useMemo(() => visiblePageItems(state.page, pages), [state.page, pages]);

  const catalogCarsDisplay = useMemo(() => {
    const deduped = dedupeSlimCarsByVin(search.result);
    return [...deduped].sort((a, b) => {
      const ta = isCatalogListedToday(a.catalog_created_at) ? 1 : 0;
      const tb = isCatalogListedToday(b.catalog_created_at) ? 1 : 0;
      if (tb !== ta) return tb - ta;
      const da = a.catalog_created_at ? Date.parse(a.catalog_created_at) : 0;
      const db = b.catalog_created_at ? Date.parse(b.catalog_created_at) : 0;
      if (Number.isFinite(db) && Number.isFinite(da) && db !== da) return db - da;
      return 0;
    });
  }, [search.result]);

  const catalogGridThumbRows = useMemo(
    () => catalogCarsDisplay.map((car) => ({ key: car.id, urls: previewImageUrls(car) })),
    [catalogCarsDisplay],
  );
  const proxiedCatalogThumbsByCar = useBatchProxiedCatalogThumbUrls(catalogGridThumbRows);

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
      const rawLabel = facetRowLabel(row);
      const val = row.value;
      let label = normalizeCatalogDisplayLabel(rawLabel) ?? rawLabel;
      if (val && f.fuels.some((x) => x.value === val)) {
        label = normalizeFuelLabel(rawLabel) ?? rawLabel;
      } else if (val && f.bodies.some((x) => x.value === val)) {
        label = displayBodyType(locale, rawLabel) ?? rawLabel;
      } else if (val && f.transmissions.some((x) => x.value === val)) {
        label = displayTransmission(locale, rawLabel) ?? rawLabel;
      } else if (val && f.colors.some((x) => x.value === val)) {
        label = displayColor(locale, rawLabel) ?? rawLabel;
      }
      map.set(row.value, label);
      const aliases = Array.isArray(row.values) && row.values.length ? row.values : [row.value];
      for (const alias of aliases) {
        if (alias) map.set(alias, label);
      }
    }
    return map;
  }, [facets, locale]);

  const popularColorRows = useMemo(() => {
    const colorFacets = facets?.colors;
    if (!colorFacets?.length) return [];
    const grouped = groupFacetRows(colorFacets, {
      labelFormatter: (row) => displayColor(locale, facetRowLabel(row)) ?? facetRowLabel(row),
    });
    return [...grouped].sort((a, b) => b.count - a.count).slice(0, 4);
  }, [facets?.colors, locale]);

  const trimFacetLabelFormatterFn = useMemo(
    () => trimFacetLabelFormatter(state, facetLabelByValue),
    [state, facetLabelByValue],
  );

  const activeChips = useMemo(
    () => buildCatalogActiveChips(state, facetLabelByValue, locale),
    [state, facetLabelByValue, locale],
  );

  const breadcrumbSegments = useMemo(
    () => catalogBreadcrumbSegments(state, facetLabelByValue, locale),
    [state, facetLabelByValue, locale],
  );

  const removeChip = useCallback(
    (chip: CatalogActiveChip) => {
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
            ? normalizeFuelLabel(facetLabelByValue.get(chip.value) ?? chip.value) ??
              (facetLabelByValue.get(chip.value) ?? chip.value)
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
    },
    [facetLabelByValue, navigate, state, toggle],
  );

  const onRetry = useCallback(() => {
    void searchQuery.refetch();
  }, [searchQuery]);

  return {
    reduceMotion,
    state,
    key,
    search,
    facets,
    loading,
    err,
    online,
    showSsrDegradedNotice,
    qDraft,
    setQDraft,
    copiedId,
    setCopiedId,
    openingCarId,
    setOpeningCarId,
    dailyNewCount,
    dailyNewLoading,
    resultsListRef,
    authenticated,
    isFavorite,
    toggleFavorite,
    navigate,
    toggle,
    reset,
    switchMarket,
    removeChip,
    onRetry,
    title,
    pages,
    pageItems,
    catalogCarsDisplay,
    proxiedCatalogThumbsByCar,
    catalogGridThumbRows,
    facetLabelByValue,
    popularColorRows,
    trimFacetLabelFormatterFn,
    activeChips,
    breadcrumbSegments,
    catalogDensity,
    setCatalogDensity,
  };
}

export type CatalogSearchController = ReturnType<typeof useCatalogSearchState>;
