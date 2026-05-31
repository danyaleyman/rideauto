import type { Market } from "@/lib/catalog-url";

export const SAVED_SEARCHES_STORAGE_KEY = "wra-saved-catalog-searches-v1";
export const SAVED_SEARCHES_MAX = 20;

export type LocalSavedSearch = {
  id: string;
  name: string;
  query: string;
  market: Market;
  createdAt: string;
};

export function readSavedSearchesLocal(): LocalSavedSearch[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = localStorage.getItem(SAVED_SEARCHES_STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as unknown;
    if (!Array.isArray(parsed)) return [];
    return parsed
      .filter(
        (x): x is LocalSavedSearch =>
          typeof x === "object" &&
          x !== null &&
          typeof (x as LocalSavedSearch).id === "string" &&
          typeof (x as LocalSavedSearch).query === "string",
      )
      .slice(0, SAVED_SEARCHES_MAX);
  } catch {
    return [];
  }
}

export function clearSavedSearchesLocal() {
  if (typeof window === "undefined") return;
  try {
    localStorage.removeItem(SAVED_SEARCHES_STORAGE_KEY);
  } catch {
    // ignore
  }
}
