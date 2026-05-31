import type { Market } from "@/lib/catalog-url";

/** Стабильные ключи TanStack Query для каталога. */
export const catalogKeys = {
  all: ["catalog"] as const,
  search: (stateKey: string) => [...catalogKeys.all, "search", stateKey] as const,
  facets: (facetKey: string) => [...catalogKeys.all, "facets", facetKey] as const,
  dailyAdditions: (market: Market) => [...catalogKeys.all, "daily", market] as const,
};
