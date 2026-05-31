export type CatalogDensity = "comfortable" | "compact";

const STORAGE_KEY = "wra-catalog-density-v1";

export function readCatalogDensity(): CatalogDensity {
  if (typeof window === "undefined") return "comfortable";
  try {
    const v = localStorage.getItem(STORAGE_KEY);
    return v === "compact" ? "compact" : "comfortable";
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
