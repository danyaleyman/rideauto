import { describe, expect, it } from "vitest";
import { canonicalTransmissionRu, transmissionSortRank } from "@/lib/vehicle-spec-ru";

describe("canonicalTransmissionRu", () => {
  it("merges automatic synonyms to АКПП", () => {
    expect(canonicalTransmissionRu("Automatic")).toBe("АКПП");
    expect(canonicalTransmissionRu("Автомат")).toBe("АКПП");
    expect(canonicalTransmissionRu("2")).toBe("АКПП");
  });

  it("merges manual synonyms to МКПП", () => {
    expect(canonicalTransmissionRu("Manual")).toBe("МКПП");
    expect(canonicalTransmissionRu("Механика")).toBe("МКПП");
    expect(canonicalTransmissionRu("1")).toBe("МКПП");
  });

  it("merges cvt synonyms", () => {
    expect(canonicalTransmissionRu("CVT")).toBe("Вариатор (CVT)");
    expect(canonicalTransmissionRu("Вариатор")).toBe("Вариатор (CVT)");
    expect(canonicalTransmissionRu("3")).toBe("Вариатор (CVT)");
    expect(
      canonicalTransmissionRu("CVT Continuously Variable Transmission (simulated 10 gears)"),
    ).toBe("Вариатор (CVT)");
  });

  it("maps che168 gearbox code 10 to cvt not stepped", () => {
    expect(canonicalTransmissionRu("10")).toBe("Вариатор (CVT)");
    expect(canonicalTransmissionRu("10-ступенчатая")).toBe("Вариатор (CVT)");
  });

  it("keeps real multi-speed labels", () => {
    expect(canonicalTransmissionRu("8-speed")).toBe("8-ступенчатая");
    expect(canonicalTransmissionRu("6")).toBe("6-ступенчатая");
  });

  it("sorts canonical types before arbitrary labels", () => {
    expect(transmissionSortRank("МКПП")).toBeLessThan(transmissionSortRank("8-ступенчатая"));
    expect(transmissionSortRank("АКПП")).toBeLessThan(transmissionSortRank("Вариатор (CVT)"));
  });
});
