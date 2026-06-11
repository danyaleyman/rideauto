import { describe, expect, it } from "vitest";
import { catalogBenchmarkEligible } from "@/lib/catalog-price-benchmark";
import type { CatalogUrlState } from "@/lib/catalog-url";

function baseState(): CatalogUrlState {
  return {
    market: "korea",
    q: "",
    marks: [],
    clusters: [],
    models: [],
    generations: [],
    trims: [],
    body: [],
    fuel: [],
    trans: [],
    color: [],
    price_from: "",
    price_to: "",
    mileage_from: "",
    mileage_to: "",
    year_from: "",
    year_to: "",
    engine_cc_from: "",
    engine_cc_to: "",
    passable_only: false,
    pricing_tier: "",
    customs_included_only: false,
    power_hp_le_160: false,
    drive_awd: false,
    no_accidents_only: false,
    new_only: false,
    sort: "date_new",
    page: 1,
  };
}

describe("catalogBenchmarkEligible", () => {
  it("requires mark and model or cluster", () => {
    expect(catalogBenchmarkEligible(baseState())).toBe(false);
    expect(
      catalogBenchmarkEligible({ ...baseState(), marks: ["Hyundai"] }),
    ).toBe(false);
    expect(
      catalogBenchmarkEligible({ ...baseState(), marks: ["Hyundai"], models: ["Sonata"] }),
    ).toBe(true);
    expect(
      catalogBenchmarkEligible({ ...baseState(), marks: ["Hyundai"], clusters: ["Sonata"] }),
    ).toBe(true);
  });
});
