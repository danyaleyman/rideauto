import { getServerApiBase } from "./env";
import type { CarDetailResponse, SearchResponse } from "./types";

function buildQuery(
  params: Record<string, string | string[] | undefined>,
  extras?: Record<string, string>,
): string {
  const usp = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined) continue;
    if (Array.isArray(v)) {
      for (const x of v) usp.append(k, x);
    } else {
      usp.set(k, v);
    }
  }
  if (extras) {
    for (const [k, v] of Object.entries(extras)) {
      if (!usp.has(k)) usp.set(k, v);
    }
  }
  const s = usp.toString();
  return s ? `?${s}` : "";
}

export async function fetchSearch(
  params: Record<string, string | string[] | undefined>,
  options?: { revalidate?: number },
): Promise<SearchResponse> {
  const base = getServerApiBase();
  const q = buildQuery(params, { per_page: "12" });
  const url = `${base}/api/search${q}`;
  const res = await fetch(url, {
    headers: { Accept: "application/json" },
    next: { revalidate: options?.revalidate ?? 30 },
  });
  if (!res.ok) {
    throw new Error(`search failed: ${res.status} ${res.statusText}`);
  }
  return res.json() as Promise<SearchResponse>;
}

export async function fetchCar(
  ref: string,
  options?: { revalidate?: number },
): Promise<CarDetailResponse> {
  const base = getServerApiBase();
  const enc = encodeURIComponent(ref);
  const url = `${base}/api/car/${enc}`;
  const res = await fetch(url, {
    headers: { Accept: "application/json" },
    next: { revalidate: options?.revalidate ?? 60 },
  });
  if (res.status === 404) {
    return { result: {} };
  }
  if (!res.ok) {
    throw new Error(`car failed: ${res.status} ${res.statusText}`);
  }
  return res.json() as Promise<CarDetailResponse>;
}
