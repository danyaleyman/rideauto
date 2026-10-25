import { describe, expect, it } from "vitest";
import {
  buildNormalizedCarTitle,
  polishChinaTrimLabel,
} from "@/lib/car-detail-data";

describe("buildNormalizedCarTitle china", () => {
  it("keeps QQ brand + short model and drops commercial dump", () => {
    expect(
      buildNormalizedCarTitle(
        "QQ New Energy",
        "Little Ant",
        "QQ New Energy Little Ant 2022 Sweet Pink Edition Half Sugar Version NCM Lithium 30kW 301km",
        "che168",
      ),
    ).toBe("QQ New Energy · Little Ant");
  });

  it("drops repeated Volkswagen and spec tail from configuration-as-generation", () => {
    expect(
      buildNormalizedCarTitle(
        "Volkswagen",
        "Tiguan",
        "Volkswagen Tiguan 2013 1.8TSI Automatic 2WD Luxury Model",
        "che168",
      ),
    ).toBe("Volkswagen · Tiguan");
  });

  it("shortens BAW (Beijing Automobile Works)", () => {
    expect(
      buildNormalizedCarTitle(
        "BAW (Beijing Automobile Works)",
        "212 Classic",
        "BAW (Beijing Automobile Works) 212 Classic 2023 Sniper 2.4T Manual Lightweight Edition",
        "che168",
      ),
    ).toBe("BAW · 212 Classic");
  });

  it("does not strip Korea generation from BMW titles", () => {
    expect(buildNormalizedCarTitle("BMW", "3 Series (F30)", "320d M Sport", "encar")).toBe(
      "BMW · 3 Series (F30) · 320d M Sport",
    );
  });
});

describe("polishChinaTrimLabel", () => {
  it("keeps edition without brand, year and powertrain", () => {
    expect(
      polishChinaTrimLabel(
        "QQ New Energy Little Ant 2022 Sweet Pink Edition Half Sugar Version NCM Lithium 30kW 301km",
        "QQ New Energy",
        "Little Ant",
      ),
    ).toBe("Sweet Pink Edition Half Sugar Version");
  });

  it("keeps Luxury from VW Tiguan dump", () => {
    expect(
      polishChinaTrimLabel(
        "Volkswagen Tiguan 2013 1.8TSI Automatic 2WD Luxury Model",
        "Volkswagen",
        "Tiguan",
      ),
    ).toBe("Luxury Model");
  });
});
