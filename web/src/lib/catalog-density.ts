export type CatalogDensity = "comfortable" | "compact";

const STORAGE_KEY = "wra-catalog-density-v1";

export function readCatalogDensity(): CatalogDensity {
  if (typeof window === "undefined") return "comfortable";
  try {
    const v = localStorage.getItem(STORAGE_KEY);
    if (v === "compact" || v === "comfortable") return v;
    // No saved preference: compact by default on narrow viewports.
    if (typeof window.matchMedia === "function" && window.matchMedia("(max-width: 767px)").matches) {
      return "compact";
    }
    return "comfortable";
  } catch {
    return "comfortable";
  }
}

export function writeCatalogDensity(value: CatalogDensity): void {
  try {
    localStorage.setItem(STORAGE_KEY, value);
  } catch {
    // ignore
  }
}
