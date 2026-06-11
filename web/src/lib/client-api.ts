"use client";

import { fetchJsonWithRetry } from "./client-fetch";
import { getPublicApiBase } from "./env";
import type { PriceBenchmarkResponse } from "@/lib/catalog-price-benchmark";
import type {
  AuthMeResponse,
  AuthSimpleOk,
  CatalogDailyAdditionsResponse,
  FacetsResponse,
  SearchResponse,
} from "./types";
import type { Market } from "./catalog-url";

async function readJson<T>(url: string, signal?: AbortSignal): Promise<T> {
  const res = await fetch(url, {
    cache: "no-store",
    headers: { Accept: "application/json" },
    signal,
  });
  if (!res.ok) {
    throw new Error(`${res.status} ${res.statusText}`);
  }
  return res.json() as Promise<T>;
}

async function readJsonReliable<T>(url: string, signal?: AbortSignal): Promise<T> {
  return fetchJsonWithRetry<T>(url, { signal, retries: 1 });
}

export function clientSearchUrl(searchParams: URLSearchParams): string {
  const base = getPublicApiBase();
  return `${base}/api/search?${searchParams.toString()}`;
}

export function clientFacetsUrl(searchParams: URLSearchParams): string {
  const base = getPublicApiBase();
  return `${base}/api/facets?${searchParams.toString()}`;
}

export function clientCatalogDailyAdditionsUrl(market: Market): string {
  const base = getPublicApiBase();
  return `${base}/api/catalog/daily-additions?region=${encodeURIComponent(market)}`;
}

export function clientCatalogPriceBenchmarkUrl(params: URLSearchParams): string {
  const base = getPublicApiBase();
  return `${base}/api/catalog/price-benchmark?${params.toString()}`;
}

export async function fetchSearchClient(
  params: URLSearchParams,
  options?: { signal?: AbortSignal },
): Promise<SearchResponse> {
  const { openApiFetchCatalogSearchAlias } = await import("@/lib/openapi-fetch-client");
  return openApiFetchCatalogSearchAlias(params, options);
}

export async function fetchFacetsClient(
  params: URLSearchParams,
  options?: { signal?: AbortSignal },
): Promise<FacetsResponse> {
  const { openApiFetchFacets } = await import("@/lib/openapi-fetch-client");
  return openApiFetchFacets(params, options);
}

export async function fetchCatalogDailyAdditions(
  market: Market,
  signal?: AbortSignal,
): Promise<CatalogDailyAdditionsResponse> {
  return readJsonReliable<CatalogDailyAdditionsResponse>(clientCatalogDailyAdditionsUrl(market), signal);
}

export async function fetchCatalogPriceBenchmark(
  params: URLSearchParams,
  signal?: AbortSignal,
): Promise<PriceBenchmarkResponse> {
  return readJsonReliable<PriceBenchmarkResponse>(clientCatalogPriceBenchmarkUrl(params), signal);
}

export async function fetchMeClient(options?: { signal?: AbortSignal }): Promise<AuthMeResponse> {
  const base = getPublicApiBase();
  return readJson<AuthMeResponse>(`${base}/api/me`, options?.signal);
}

export async function requestMagicLinkClient(
  email: string,
  options?: { signal?: AbortSignal },
): Promise<AuthSimpleOk> {
  const base = getPublicApiBase();
  const res = await fetch(`${base}/api/auth/magic/request`, {
    method: "POST",
    cache: "no-store",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: JSON.stringify({ email }),
    signal: options?.signal,
  });
  if (!res.ok) {
    throw new Error(`${res.status} ${res.statusText}`);
  }
  return (await res.json()) as AuthSimpleOk;
}

export async function verifyMagicLinkClient(
  token: string,
  options?: { signal?: AbortSignal },
): Promise<AuthSimpleOk> {
  const base = getPublicApiBase();
  const res = await fetch(`${base}/api/auth/magic/verify`, {
    method: "POST",
    cache: "no-store",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: JSON.stringify({ token }),
    signal: options?.signal,
  });
  if (!res.ok) {
    throw new Error(`${res.status} ${res.statusText}`);
  }
  return (await res.json()) as AuthSimpleOk;
}

export async function logoutClient(options?: { signal?: AbortSignal }): Promise<AuthSimpleOk> {
  const base = getPublicApiBase();
  const res = await fetch(`${base}/api/auth/logout`, {
    method: "POST",
    cache: "no-store",
    headers: { Accept: "application/json" },
    signal: options?.signal,
  });
  if (!res.ok) {
    throw new Error(`${res.status} ${res.statusText}`);
  }
  return (await res.json()) as AuthSimpleOk;
}

export async function fetchFavoritesClient(options?: { signal?: AbortSignal }): Promise<{
  result: Array<{ id: string; title: string; price: number | null; addedAt: number }>;
}> {
  const base = getPublicApiBase();
  return readJson(`${base}/api/favorites`, options?.signal);
}

export async function addFavoriteClient(carId: string, options?: { signal?: AbortSignal }): Promise<AuthSimpleOk> {
  const base = getPublicApiBase();
  const res = await fetch(`${base}/api/favorites/${encodeURIComponent(carId)}`, {
    method: "POST",
    cache: "no-store",
    headers: { Accept: "application/json" },
    signal: options?.signal,
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return (await res.json()) as AuthSimpleOk;
}

export async function removeFavoriteClient(
  carId: string,
  options?: { signal?: AbortSignal },
): Promise<AuthSimpleOk> {
  const base = getPublicApiBase();
  const res = await fetch(`${base}/api/favorites/${encodeURIComponent(carId)}`, {
    method: "DELETE",
    cache: "no-store",
    headers: { Accept: "application/json" },
    signal: options?.signal,
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return (await res.json()) as AuthSimpleOk;
}

export async function importFavoritesClient(
  carIds: string[],
  options?: { signal?: AbortSignal },
): Promise<AuthSimpleOk> {
  const base = getPublicApiBase();
  const res = await fetch(`${base}/api/favorites/import`, {
    method: "POST",
    cache: "no-store",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: JSON.stringify({ car_ids: carIds }),
    signal: options?.signal,
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return (await res.json()) as AuthSimpleOk;
}

export type SubscriptionItem = {
  id: string;
  name: string;
  filters: Record<string, unknown>;
  query_string: string;
  market: Market;
  notify_enabled: boolean;
  last_notified_at: string | null;
  created_at: string | null;
};

export async function fetchSubscriptionsClient(options?: {
  signal?: AbortSignal;
}): Promise<{ result: SubscriptionItem[] }> {
  const base = getPublicApiBase();
  return readJson(`${base}/api/subscriptions`, options?.signal);
}

export async function createSubscriptionClient(
  payload: {
    name: string;
    filters: Record<string, string>;
    query_string: string;
    market: Market;
    notify_enabled?: boolean;
  },
  options?: { signal?: AbortSignal },
): Promise<AuthSimpleOk> {
  const base = getPublicApiBase();
  const res = await fetch(`${base}/api/subscriptions`, {
    method: "POST",
    cache: "no-store",
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: JSON.stringify(payload),
    signal: options?.signal,
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return (await res.json()) as AuthSimpleOk;
}

export async function deleteSubscriptionClient(
  id: string,
  options?: { signal?: AbortSignal },
): Promise<AuthSimpleOk> {
  const base = getPublicApiBase();
  const res = await fetch(`${base}/api/subscriptions/${encodeURIComponent(id)}`, {
    method: "DELETE",
    cache: "no-store",
    credentials: "include",
    headers: { Accept: "application/json" },
    signal: options?.signal,
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return (await res.json()) as AuthSimpleOk;
}

export async function patchSubscriptionClient(
  id: string,
  payload: { notify_enabled?: boolean; name?: string },
  options?: { signal?: AbortSignal },
): Promise<AuthSimpleOk> {
  const base = getPublicApiBase();
  const res = await fetch(`${base}/api/subscriptions/${encodeURIComponent(id)}`, {
    method: "PATCH",
    cache: "no-store",
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: JSON.stringify(payload),
    signal: options?.signal,
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return (await res.json()) as AuthSimpleOk;
}

export type CompareCarRow = {
  id: string;
  title: string;
  mark?: string | null;
  model?: string | null;
  year?: string | number | null;
  mileage_km?: number | null;
  price_rub?: number | null;
  fuel?: string | null;
  transmission?: string | null;
  power_hp?: number | null;
  body_type?: string | null;
  drive_type?: string | null;
  source?: string | null;
  thumb_url?: string | null;
  url_path: string;
};

export async function fetchCompareClient(
  ids: string[],
  options?: { signal?: AbortSignal },
): Promise<{ result: CompareCarRow[] }> {
  const base = getPublicApiBase();
  const q = ids.map((id) => encodeURIComponent(id)).join(",");
  return readJsonReliable(`${base}/api/compare?ids=${q}`, options?.signal);
}

export async function translateTextClient(
  text: string,
  options?: { signal?: AbortSignal; provider?: "openai" | "deepseek" },
): Promise<{ translated_text: string; provider: string; model: string; cached: boolean }> {
  const base = getPublicApiBase();
  const res = await fetch(`${base}/api/translate`, {
    method: "POST",
    cache: "no-store",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: JSON.stringify({
      text,
      target_lang: "ru",
      ...(options?.provider ? { provider: options.provider } : {}),
    }),
    signal: options?.signal,
  });
  if (!res.ok) {
    throw new Error(`${res.status} ${res.statusText}`);
  }
  return (await res.json()) as { translated_text: string; provider: string; model: string; cached: boolean };
}
