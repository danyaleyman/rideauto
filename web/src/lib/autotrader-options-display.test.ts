import { describe, expect, it } from "vitest";
import {
  classifyAutotraderOptionGroup,
  displayAutotraderOptionRu,
  isAutotraderOptionNoise,
} from "@/lib/autotrader-options-display";

describe("autotrader-options-display", () => {
  it("maps common English features to Russian", () => {
    expect(displayAutotraderOptionRu("Adaptive Cruise Control")).toBe("Адаптивный круиз-контроль");
    expect(displayAutotraderOptionRu("Apple CarPlay & Android Auto")).toBe(
      "Apple CarPlay и Android Auto",
    );
    expect(displayAutotraderOptionRu("Heated Front Seat(s)")).toBe("Подогрев передних сидений");
    expect(displayAutotraderOptionRu("ABS brakes")).toBe("ABS");
  });

  it("dedupes casing variants to the same RU label", () => {
    expect(displayAutotraderOptionRu("Power steering")).toBe(
      displayAutotraderOptionRu("Power Steering"),
    );
    expect(displayAutotraderOptionRu("Rain sensing wipers")).toBe(
      displayAutotraderOptionRu("Rain Sensing Wipers"),
    );
  });

  it("filters noise", () => {
    expect(isAutotraderOptionNoise("SHIMMERING SILVER")).toBe(true);
    expect(isAutotraderOptionNoise("Requires Subscription")).toBe(true);
    expect(isAutotraderOptionNoise("Option Group 01")).toBe(true);
    expect(displayAutotraderOptionRu("SHIMMERING SILVER")).toBe("");
  });

  it("classifies RU labels into groups", () => {
    expect(classifyAutotraderOptionGroup("Адаптивный круиз-контроль")).toBe("assist");
    expect(classifyAutotraderOptionGroup("Подушка безопасности для коленей")).toBe("safety");
    expect(classifyAutotraderOptionGroup("Wi‑Fi точка доступа")).toBe("media");
  });
});
