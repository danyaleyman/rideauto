import { afterEach, describe, expect, it, vi } from "vitest";
import { readCatalogDensity, resolveCatalogView } from "@/lib/catalog-density";

describe("readCatalogDensity", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("uses saved view when present", () => {
    const store = new Map<string, string>([["wra-catalog-view-v1", "tile"]]);
    vi.stubGlobal("window", {});
    vi.stubGlobal("localStorage", {
      getItem: (k: string) => store.get(k) ?? null,
      setItem: (k: string, v: string) => store.set(k, v),
      clear: () => store.clear(),
    });
    expect(readCatalogDensity()).toBe("tile");
  });

  it("migrates legacy comfortable/compact to list", () => {
    const store = new Map<string, string>([["wra-catalog-density-v1", "comfortable"]]);
    vi.stubGlobal("window", {});
    vi.stubGlobal("localStorage", {
      getItem: (k: string) => store.get(k) ?? null,
      setItem: (k: string, v: string) => store.set(k, v),
      clear: () => store.clear(),
    });
    expect(readCatalogDensity()).toBe("list");
  });

  it("defaults to list without preference", () => {
    vi.stubGlobal("window", {});
    vi.stubGlobal("localStorage", {
      getItem: () => null,
      setItem: () => undefined,
      clear: () => undefined,
    });
    expect(readCatalogDensity()).toBe("list");
  });
});

describe("resolveCatalogView", () => {
  it("keeps table on desktop and falls back to list on mobile", () => {
    expect(resolveCatalogView("table", true)).toBe("table");
    expect(resolveCatalogView("table", false)).toBe("list");
    expect(resolveCatalogView("tile", false)).toBe("tile");
  });
});
