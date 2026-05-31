import { describe, expect, it } from "vitest";
import { enrichChe168CarSpecs } from "@/lib/che168-spec-enrich";

describe("enrichChe168CarSpecs", () => {
  it("prefers Abbreviation transmission and converts kW power to hp", () => {
    const raw = {
      paramtypeitems: [
        {
          paramitems: [
            { name: "Maximum power (kW)", value: "190" },
            { name: "Maximum horsepower (Ps)", value: "258" },
            { name: "Max Torque (N·m)", value: "400" },
            { name: "Abbreviation", value: "8-speed automatic with manual shift mode" },
            { name: "Drive Type", value: "--" },
            { name: "Displacement (L)", value: "2.0" },
          ],
        },
      ],
    };
    const out = enrichChe168CarSpecs({
      source: "che168",
      transmission_type: "8-speed",
      drive_type: "--",
      power_hp: 190,
      che168_params_raw: raw,
    });
    expect(out.transmission_type).toBe("8-speed automatic with manual shift mode");
    expect(out.power_hp).toBe(258);
    expect(out.torque_nm).toBe(400);
    expect(out.displacement_liters_label).toBe("2.0");
    expect(out.drive_type).toBeUndefined();
  });

  it("Corolla: 116 hp from Engine/Ps, not top speed 180", () => {
    const raw = {
      paramitems: [
        { name: "Top speed (km/h)", value: "180" },
        { name: "Maximum power (kW)", value: "85" },
        { name: "Maximum horsepower (Ps)", value: "116" },
        { name: "Engine", value: "1.2T 116HP L4" },
        { name: "Abbreviation", value: "CVT Continuously Variable Transmission (simulated 10 gears)" },
      ],
    };
    const out = enrichChe168CarSpecs({
      source: "che168",
      power_hp: 85,
      transmission_type: "10",
      che168_params_raw: raw,
    });
    expect(out.power_hp).toBe(116);
    expect(out.transmission_type).toContain("CVT");
    expect(out.transmission_type_ru).toContain("CVT");
  });
});
