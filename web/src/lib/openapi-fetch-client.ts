/**
 * Типизированный HTTP-клиент из OpenAPI (`npm run generate:api-types`).
 * Для эндпоинтов вне схемы (например legacy alias) — fallback на fetchJsonWithRetry.
 */
import createClient from "openapi-fetch";
import type { paths } from "@/lib/generated/openapi";
import { fetchJsonWithRetry } from "@/lib/client-fetch";
import { getPublicApiBase } from "@/lib/env";
import type { FacetsResponse, SearchResponse } from "@/lib/types";
import { assertSearchResponse } from "@/lib/api-contract";

let client: ReturnType<typeof createClient<paths>> | null = null;

export function getOpenApiClient() {
  if (!client) {
    client = createClient<paths>({ baseUrl: getPublicApiBase() });
  }
  return client;
}

/** Каталог: GET /api/cars (в UI также /api/search — тот же handler). */
export async function openApiFetchCatalog(
  searchParams: URLSearchParams,
  options?: { signal?: AbortSignal },
): Promise<SearchResponse> {
  const query = Object.fromEntries(searchParams.entries()) as Record<string, string>;
  const { data, error, response } = await getOpenApiClient().GET("/api/cars", {
    params: { query },
    signal: options?.signal,
  });
  if (error || !response.ok) {
    throw new Error(`${response.status} ${response.statusText}`);
  }
  const body = data as unknown as SearchResponse;
  if (process.env.NODE_ENV !== "production") {
    try {
      assertSearchResponse(body);
    } catch (e) {
      console.warn("[openapi] catalog contract", e);
    }
  }
  return body;
}

/** Каталог через alias `/api/search` (типизировано в OpenAPI). */
export async function openApiFetchCatalogSearchAlias(
  searchParams: URLSearchParams,
  options?: { signal?: AbortSignal },
): Promise<SearchResponse> {
  const query = Object.fromEntries(searchParams.entries()) as Record<string, string>;
  const { data, error, response } = await getOpenApiClient().GET("/api/search", {
    params: { query },
    signal: options?.signal,
  });
  if (error || !response.ok) {
    const base = getPublicApiBase();
    const url = `${base}/api/search?${searchParams.toString()}`;
    const body = await fetchJsonWithRetry<SearchResponse>(url, {
      signal: options?.signal,
      retries: 1,
    });
    if (process.env.NODE_ENV !== "production") {
      try {
        assertSearchResponse(body);
      } catch (e) {
        console.warn("[openapi] search fallback contract", e);
      }
    }
    return body;
  }
  const body = data as unknown as SearchResponse;
  if (process.env.NODE_ENV !== "production") {
    try {
      assertSearchResponse(body);
    } catch (e) {
      console.warn("[openapi] search contract", e);
    }
  }
  return body;
}

/** Фасеты: GET /api/facets */
export async function openApiFetchFacets(
  searchParams: URLSearchParams,
  options?: { signal?: AbortSignal },
): Promise<FacetsResponse> {
  const query = Object.fromEntries(searchParams.entries()) as Record<string, string>;
  const { data, error, response } = await getOpenApiClient().GET("/api/facets", {
    params: { query },
    signal: options?.signal,
  });
  if (error || !response.ok) {
    const base = getPublicApiBase();
    const url = `${base}/api/facets?${searchParams.toString()}`;
    return fetchJsonWithRetry<FacetsResponse>(url, {
      signal: options?.signal,
      retries: 1,
    });
  }
  return data as unknown as FacetsResponse;
}
