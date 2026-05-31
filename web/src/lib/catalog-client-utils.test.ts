import { describe, expect, it } from "vitest";
import { catalogCardAttributeChips, previewImageUrls } from "@/lib/catalog-client-utils";

describe("catalogCardAttributeChips", () => {
  it("builds year, km, fuel, displacement and hp chips", () => {
    const chips = catalogCardAttributeChips(
      {
        km_age: 42_000,
        engine_type: "gasoline",
        displacement_cc: 1600,
        power_hp: 180,
      },
      2021,
    );
    const keys = chips.map((c) => c.key);
    expect(keys).toContain("y");
    expect(keys).toContain("km");
    expect(keys).toContain("fuel");
    expect(keys).toContain("cc");
    expect(keys).toContain("hp");
    expect(chips.find((c) => c.key === "hp")?.label).toMatch(/180/);
    expect(chips.find((c) => c.key === "cc")?.label).toMatch(/1[.,]6.*литр/);
  });

  it("skips displacement chip for electric fuel", () => {
    const chips = catalogCardAttributeChips(
      {
        engine_type: "electric",
        displacement_cc: 0,
        power_hp: 204,
      },
      2023,
    );
    expect(chips.some((c) => c.key === "cc")).toBe(false);
  });
});

describe("previewImageUrls", () => {
  it("returns up to three image URLs from car data", () => {
    const urls = previewImageUrls({
      id: "x",
      data: {
        images: ["https://a/1.jpg", "https://a/2.jpg", "https://a/3.jpg", "https://a/4.jpg"],
      },
    });
    expect(urls).toHaveLength(4);
    expect(urls[0]).toContain("1.jpg");
  });
});
