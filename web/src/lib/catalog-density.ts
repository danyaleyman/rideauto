export type CatalogDensity = "list" | "tile" | "table";

const STORAGE_KEY = "wra-catalog-view-v1";
const LEGACY_KEY = "wra-catalog-density-v1";

function parseCatalogDensity(value: string | null): CatalogDensity | null {
  if (value === "list" || value === "tile" || value === "table") return value;
  if (value === "comfortable" || value === "compact") return "list";
  return null;
}

export function readCatalogDensity(): CatalogDensity {
  if (typeof window === "undefined") return "list";
  try {
    const next = parseCatalogDensity(localStorage.getItem(STORAGE_KEY));
    if (next) return next;
    return parseCatalogDensity(localStorage.getItem(LEGACY_KEY)) ?? "list";
  } catch {
    return "list";
  }
}

export function writeCatalogDensity(value: CatalogDensity): void {
  try {
    localStorage.setItem(STORAGE_KEY, value);
  } catch {
    // ignore
  }
}

/** Таблица только на десктопе — на узком экране остаётся список. */
export function resolveCatalogView(density: CatalogDensity, desktop: boolean): CatalogDensity {
  if (density === "table" && !desktop) return "list";
  return density;
}
