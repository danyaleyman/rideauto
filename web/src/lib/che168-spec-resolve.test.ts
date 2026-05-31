import { describe, expect, it } from "vitest";
import {
  classifyChe168PowerLabel,
  resolveChe168PowerHp,
} from "@/lib/che168-spec-resolve";

describe("resolveChe168PowerHp", () => {
  const corollaRaw = {
    paramitems: [
      { name: "Top speed (km/h)", value: "180" },
      { name: "Maximum power (kW)", value: "85" },
      { name: "Maximum horsepower (Ps)", value: "116" },
      { name: "Max Torque (N·m)", value: "185" },
      { name: "Engine", value: "1.2T 116HP L4" },
      { name: "Abbreviation", value: "CVT Continuously Variable Transmission (simulated 10 gears)" },
    ],
  };

  it("does not treat top speed as horsepower", () => {
    expect(classifyChe168PowerLabel("Top speed (km/h)")).toBe("skip");
    expect(resolveChe168PowerHp(corollaRaw)).toBe(116);
  });

  it("prefers engine line hp over kW", () => {
    expect(resolveChe168PowerHp(corollaRaw, "")).toBe(116);
  });

  it("converts kW when no hp fields", () => {
    const raw = {
      paramitems: [
        { name: "Maximum power (kW)", value: "85" },
        { name: "Top speed (km/h)", value: "180" },
      ],
    };
    expect(resolveChe168PowerHp(raw)).toBe(116);
  });

  it("handles BMW-style 258 ps vs 190 kw", () => {
    const raw = {
      paramitems: [
        { name: "Maximum power (kW)", value: "190" },
        { name: "Maximum horsepower (Ps)", value: "258" },
        { name: "Engine", value: "2.0T 258hp L4" },
      ],
    };
    expect(resolveChe168PowerHp(raw)).toBe(258);
  });
});
