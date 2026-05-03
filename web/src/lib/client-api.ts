"use client";

import { fetchJsonWithRetry } from "./client-fetch";
import { getPublicApiBase } from "./env";
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

export async function fetchSearchClient(
  params: URLSearchParams,
  options?: { signal?: AbortSignal },
): Promise<SearchResponse> {
  return readJsonReliable<SearchResponse>(clientSearchUrl(params), options?.signal);
}

export async function fetchFacetsClient(
  params: URLSearchParams,
  options?: { signal?: AbortSignal },
): Promise<FacetsResponse> {
  return readJsonReliable<FacetsResponse>(clientFacetsUrl(params), options?.signal);
}

export async function fetchCatalogDailyAdditions(
  market: Market,
  signal?: AbortSignal,
): Promise<CatalogDailyAdditionsResponse> {
  return readJsonReliable<CatalogDailyAdditionsResponse>(clientCatalogDailyAdditionsUrl(market), signal);
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
