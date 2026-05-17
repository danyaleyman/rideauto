import { describe, expect, it } from "vitest";
import { buildPriceBreakdownRows, isChinaListing } from "@/lib/car-price-breakdown";

describe("buildPriceBreakdownRows", () => {
  it("hides excise/vat and mislabeled docs for Korea ICE", () => {
    const rows = buildPriceBreakdownRows({
      priceRub: 3_133_280,
      priceWon: 2_450,
      carId: "41982259",
      calcDetails: {
        source: "encar",
        engine_type: "Бензин",
        pricing_tier: "full_customs",
        duty_rub: 476_428,
        customs_fee_rub: 11_746,
        util_rub: 1_485_978,
        excise_rub: 0,
        vat_rub: 0,
        customs_total_rub: 1_974_152,
        freight_rub: 95_000,
        documents_krw_rub: 28_000,
        broker_rub: 86_000,
        commission_rub: 150_000,
        cbr_krw_rub_per_won: 0.055,
      },
    });
    const labels = rows.flatMap((r) => [r.label, ...(r.subRows?.map((s) => s.label) ?? [])]);
    expect(labels).not.toContain("Акциз (СТП)");
    expect(labels).not.toContain("НДС (СТП)");
    expect(labels).not.toContain("СБКТС / ЭПТС / регистрационные платежи");
    expect(labels).toContain("Оформление документов (Корея)");
    expect(labels).toContain("Доставка / фрахт");
    expect(labels).toContain("Комиссия Ride Auto");
    expect(labels).toContain("Брокерские услуги");
    expect(rows.some((r) => r.label === "Цена в объявлении (воны)" && r.value.includes("("))).toBe(true);
  });

  it("maps China docs to logistics", () => {
    const rows = buildPriceBreakdownRows({
      priceRub: 7_000_000,
      priceCny: 584_500,
      carId: "che168-1",
      calcDetails: {
        source: "che168",
        pricing_tier: "full_customs",
        china_docs_delivery_rub: 162_000,
        vtb_bank_transfer_rub: 140_000,
        freight_rub: 0,
        broker_rub: 86_000,
        commission_rub: 300_000,
        cny_rub: 10.68,
        customs_total_rub: 500_000,
        duty_rub: 400_000,
      },
    });
    const labels = rows.flatMap((r) => [r.label, ...(r.subRows?.map((s) => s.label) ?? [])]);
    expect(isChinaListing({ source: "che168" }, "che168-1")).toBe(true);
    expect(labels).toContain("Оформление в Китае и доставка до таможни");
    expect(labels).not.toContain("СБКТС / ЭПТС / регистрационные платежи");
    expect(labels).toContain("Цена в объявлении (CNY)");
  });
});
