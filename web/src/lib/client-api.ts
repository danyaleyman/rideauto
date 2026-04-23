"use client";

import { getPublicApiBase } from "./env";
import type { CatalogDailyAdditionsResponse, FacetsResponse, SearchResponse } from "./types";
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
  return readJson<SearchResponse>(clientSearchUrl(params), options?.signal);
}

export async function fetchFacetsClient(
  params: URLSearchParams,
  options?: { signal?: AbortSignal },
): Promise<FacetsResponse> {
  return readJson<FacetsResponse>(clientFacetsUrl(params), options?.signal);
}

export async function fetchCatalogDailyAdditions(
  market: Market,
  signal?: AbortSignal,
): Promise<CatalogDailyAdditionsResponse> {
  return readJson<CatalogDailyAdditionsResponse>(clientCatalogDailyAdditionsUrl(market), signal);
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
