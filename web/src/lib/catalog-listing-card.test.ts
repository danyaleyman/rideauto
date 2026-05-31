import { describe, expect, it } from "vitest";
import { buildCatalogCardDisplayData } from "@/lib/catalog-listing-card";
import type { SlimCar } from "@/lib/types";

describe("buildCatalogCardDisplayData", () => {
  it("merges read_model into card data and builds title", () => {
    const car: SlimCar = {
      id: "c1",
      title: "Fallback",
      year_num: 2021,
      data: { mark: "Hyundai", model: "Sonata" },
    };
    (car as Record<string, unknown>).read_model = { mileage_km: 42_000, year: 2020 };
    const { cardData, normalizedTitle } = buildCatalogCardDisplayData(car);
    expect(cardData.km_age).toBe(42_000);
    expect(cardData.year).toBe(2020);
    expect(normalizedTitle.toLowerCase()).toContain("hyundai");
  });

  it("corrects che168 power_hp from che168_params_raw for catalog chips", () => {
    const raw = {
      paramitems: [
        { name: "Maximum power (kW)", value: "186" },
        { name: "Maximum horsepower (Ps)", value: "253" },
      ],
    };
    const car: SlimCar = {
      id: "che168-58463208",
      title: "Test",
      data: {
        source: "che168",
        engine_type: "Gasoline",
        power_hp: 186,
        che168_params_raw: raw,
      },
    };
    const { cardData } = buildCatalogCardDisplayData(car);
    expect(cardData.power_hp).toBe(253);
  });
});
