import { describe, expect, it } from "vitest";
import type { SlimCar } from "./types";
import { dedupeSlimCarsByVin, normalizeVinForCatalogDedupe } from "./catalog-vin-dedupe";

describe("normalizeVinForCatalogDedupe", () => {
  it("uppercases, strips spaces and hyphens", () => {
    expect(normalizeVinForCatalogDedupe(" ab1 cd-efg12345 ")).toBe("AB1CDEFG12345");
  });

  it("returns empty for short strings", () => {
    expect(normalizeVinForCatalogDedupe("SHORT")).toBe("");
    expect(normalizeVinForCatalogDedupe("")).toBe("");
  });
});

describe("dedupeSlimCarsByVin", () => {
  it("keeps newest by catalog_updated_at and preserves order of first occurrence", () => {
    const a: SlimCar = {
      id: "a",
      catalog_updated_at: "2020-01-01T00:00:00.000Z",
      data: { vin: "1HGBH41JXMN109186" },
    };
    const b: SlimCar = {
      id: "b",
      catalog_updated_at: "2021-01-01T00:00:00.000Z",
      data: { vin: "1hgbh41jxmn109186" },
    };
    const out = dedupeSlimCarsByVin([a, b]);
    expect(out).toHaveLength(1);
    expect(out[0]!.id).toBe("b");
  });

  it("leaves cars without VIN in list", () => {
    const x: SlimCar = { id: "x", data: {} };
    const y: SlimCar = { id: "y", data: { vin: "1HGBH41JXMN109186" } };
    const out = dedupeSlimCarsByVin([x, y]);
    expect(out.map((c) => c.id).sort()).toEqual(["x", "y"]);
  });
});
