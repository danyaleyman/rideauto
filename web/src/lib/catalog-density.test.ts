import { afterEach, describe, expect, it, vi } from "vitest";
import { readCatalogDensity } from "@/lib/catalog-density";

describe("readCatalogDensity", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("uses saved preference when present", () => {
    const store = new Map<string, string>([["wra-catalog-density-v1", "comfortable"]]);
    vi.stubGlobal("window", {
      matchMedia: () => ({ matches: true }),
    });
    vi.stubGlobal("localStorage", {
      getItem: (k: string) => store.get(k) ?? null,
      setItem: (k: string, v: string) => store.set(k, v),
      clear: () => store.clear(),
    });
    expect(readCatalogDensity()).toBe("comfortable");
  });

  it("defaults to compact on narrow viewports without preference", () => {
    vi.stubGlobal("window", {
      matchMedia: (query: string) => ({
        matches: query.includes("max-width: 767px"),
      }),
    });
    vi.stubGlobal("localStorage", {
      getItem: () => null,
      setItem: () => undefined,
      clear: () => undefined,
    });
    expect(readCatalogDensity()).toBe("compact");
  });
});
