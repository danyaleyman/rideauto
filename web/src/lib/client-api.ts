"use client";

import { getPublicApiBase } from "./env";
import type { FacetsResponse, SearchResponse } from "./types";

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
