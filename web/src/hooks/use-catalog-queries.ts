"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { assertSearchResponse } from "@/lib/api-contract";
import {
  fetchCatalogDailyAdditions,
  fetchFacetsClient,
  fetchSearchClient,
} from "@/lib/client-api";
import { sendCatalogDiagEvent } from "@/lib/catalog-diagnostics";
import type { CatalogUrlState, Market } from "@/lib/catalog-url";
import { toApiSearchParams, toFacetApiParams } from "@/lib/catalog-url";
import { reportClientError } from "@/lib/observability";
import type { SearchResponse } from "@/lib/types";
import { catalogKeys } from "@/hooks/catalog-query-keys";

const CATALOG_SEARCH_STALE_MS = 30_000;
const CATALOG_FACETS_STALE_MS = 60_000;
const CATALOG_DAILY_STALE_MS = 5 * 60_000;

export function useCatalogSearchQuery(args: {
  key: string;
  state: CatalogUrlState;
  initialSearch: SearchResponse;
  ssrKey: string;
  ssrDegraded: boolean;
  diagEnabled: boolean;
}) {
  const { key, state, initialSearch, ssrKey, ssrDegraded, diagEnabled } = args;
  const hydrateFromSsr = !ssrDegraded && key === ssrKey;

  return useQuery({
    queryKey: catalogKeys.search(key),
    queryFn: async ({ signal }) => {
      const started = Date.now();
      const sq = toApiSearchParams(state);
      sendCatalogDiagEvent(
        diagEnabled,
        "catalog_search_start",
        { key, query: sq.toString(), page: state.page },
        { market: state.market },
      );
      try {
        const sRes = await fetchSearchClient(sq, { signal });
        if (process.env.NODE_ENV !== "production") {
          try {
            assertSearchResponse(sRes);
          } catch (contractErr) {
            reportClientError(contractErr, { area: "catalog_search_contract", key });
          }
        }
        sendCatalogDiagEvent(
          diagEnabled,
          "catalog_search_ok",
          {
            key,
            duration_ms: Date.now() - started,
            total: sRes.meta?.total ?? null,
            result_len: sRes.result?.length ?? null,
          },
          { market: state.market },
        );
        return sRes;
      } catch (e) {
        sendCatalogDiagEvent(
          diagEnabled,
          "catalog_search_failed",
          {
            key,
            duration_ms: Date.now() - started,
            error: e instanceof Error ? e.message : "unknown",
          },
          { level: "error", market: state.market },
        );
        reportClientError(e, { area: "catalog_search", key, page: state.page });
        throw e;
      }
    },
    initialData: hydrateFromSsr ? initialSearch : undefined,
    placeholderData: keepPreviousData,
    staleTime: CATALOG_SEARCH_STALE_MS,
  });
}

export function useCatalogFacetsQuery(args: {
  facetKey: string;
  facetState: CatalogUrlState;
  diagEnabled: boolean;
  market: Market;
}) {
  const { facetKey, facetState, diagEnabled, market } = args;

  return useQuery({
    queryKey: catalogKeys.facets(facetKey),
    queryFn: async ({ signal }) => {
      const started = Date.now();
      const fq = toFacetApiParams(facetState);
      sendCatalogDiagEvent(
        diagEnabled,
        "catalog_facets_start",
        { facet_key: facetKey, query: fq.toString() },
        { market },
      );
      try {
        const fRes = await fetchFacetsClient(fq, { signal });
        sendCatalogDiagEvent(
          diagEnabled,
          "catalog_facets_ok",
          {
            facet_key: facetKey,
            duration_ms: Date.now() - started,
            marks_len: fRes.marks?.length ?? null,
          },
          { market },
        );
        return fRes;
      } catch (e) {
        sendCatalogDiagEvent(
          diagEnabled,
          "catalog_facets_failed",
          {
            facet_key: facetKey,
            duration_ms: Date.now() - started,
            error: e instanceof Error ? e.message : "unknown",
          },
          { level: "error", market },
        );
        console.error("facets fetch failed", e);
        throw e;
      }
    },
    staleTime: CATALOG_FACETS_STALE_MS,
  });
}

export function useCatalogDailyAdditionsQuery(market: Market) {
  return useQuery({
    queryKey: catalogKeys.dailyAdditions(market),
    queryFn: ({ signal }) => fetchCatalogDailyAdditions(market, signal),
    staleTime: CATALOG_DAILY_STALE_MS,
  });
}

/** @internal тесты */
export const catalogQueryStaleMs = {
  search: CATALOG_SEARCH_STALE_MS,
  facets: CATALOG_FACETS_STALE_MS,
  daily: CATALOG_DAILY_STALE_MS,
} as const;
