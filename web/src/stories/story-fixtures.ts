"use client";

import type { CatalogSearchController } from "@/hooks/use-catalog-search-state";
import { parseCatalogUrl } from "@/lib/catalog-url";
import type { SlimCar } from "@/lib/types";

/** Minimal catalog controller for Storybook (not a live search hook). */
export function createStoryCatalogMock(
  overrides: Partial<CatalogSearchController> = {},
): CatalogSearchController {
  const base = {
    reduceMotion: true,
    state: parseCatalogUrl(new URLSearchParams()),
    qDraft: "",
    setQDraft: () => {},
    navigate: () => {},
    loading: false,
    err: null,
    search: {
      result: [],
      meta: { total: 0, limit: 24, per_page: 24, pages: 0, offset: 0 },
    },
    reset: () => {},
    copiedId: null,
    setCopiedId: () => {},
    openingCarId: null,
    setOpeningCarId: () => {},
    authenticated: false,
    isFavorite: () => false,
    toggleFavorite: async () => {},
    proxiedCatalogThumbsByCar: new Map(),
    catalogDensity: "comfortable" as const,
    setCatalogDensity: () => {},
  };
  return { ...base, ...overrides } as CatalogSearchController;
}

export const storySlimCar: SlimCar = {
  id: "story-bmw-320",
  title: "BMW 320i xDrive",
  price: 2_450_000,
  pricing_tier: "full_customs",
  customs_included: true,
  year_num: 2021,
  catalog_created_at: new Date().toISOString(),
  data: {
    mark: "BMW",
    model: "3 Series",
    year: 2021,
    mileage: 45000,
    fuel: "Бензин",
    transmission: "Автомат",
    images: ["/assets/korea-fallback-image.png"],
  },
};
