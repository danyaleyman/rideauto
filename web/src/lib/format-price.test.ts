import { describe, expect, it } from "vitest";
import { formatCatalogCardPrice, formatPriceLabel, PRICE_ON_REQUEST_RU } from "./format-price";

describe("formatPriceLabel", () => {
  it("formats RUB with ru locale", () => {
    const s = formatPriceLabel(1_650_000);
    expect(s.replace(/\s/g, "")).toMatch(/1.*650.*000/);
    expect(s).toContain("₽");
  });

  it("returns em dash for null/NaN", () => {
    expect(formatPriceLabel(null)).toBe("—");
    expect(formatPriceLabel(undefined)).toBe("—");
    expect(formatPriceLabel(Number.NaN)).toBe("—");
  });
});

describe("formatCatalogCardPrice", () => {
  it("respects price_on_request flag", () => {
    expect(formatCatalogCardPrice(100, true)).toBe(PRICE_ON_REQUEST_RU);
  });

  it("uses formatted price when present", () => {
    const s = formatCatalogCardPrice(1_000_000, false);
    expect(s).not.toBe(PRICE_ON_REQUEST_RU);
    expect(s).toContain("₽");
  });

  it("treats non-positive as on request", () => {
    expect(formatCatalogCardPrice(0)).toBe(PRICE_ON_REQUEST_RU);
    expect(formatCatalogCardPrice(-1)).toBe(PRICE_ON_REQUEST_RU);
  });
});
