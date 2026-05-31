import { describe, expect, it } from "vitest";
import {
  collectBodyRows,
  hasStructuredBodyPayload,
  normalizeBodyStatus,
} from "@/lib/car-body-panels";

describe("normalizeBodyStatus", () => {
  it("maps Korean replacement tokens", () => {
    expect(normalizeBodyStatus("교환")).toBe("Замена");
    expect(normalizeBodyStatus("도장")).toBe("Окрас");
  });
});

describe("hasStructuredBodyPayload", () => {
  it("returns false for empty payloads", () => {
    expect(hasStructuredBodyPayload(null, null, null, null, null, null)).toBe(false);
  });

  it("returns true when diagnosisItems present", () => {
    expect(
      hasStructuredBodyPayload(null, null, null, null, null, [{ name: "HOOD", resultCode: "NORMAL" }]),
    ).toBe(true);
  });
});

describe("collectBodyRows", () => {
  it("maps Encar diagnosis item codes to Russian parts", () => {
    const { external } = collectBodyRows({
      outers: null,
      bodyPanels: null,
      bodyChanged: null,
      paintPartTypes: null,
      seriousTypes: null,
      diagnosisItems: [{ name: "HOOD", resultCode: "PAINT" }],
    });
    const hood = external.find((r) => r.part === "Капот");
    expect(hood?.status).toBe("Окрас");
  });

  it("dedupes by part keeping worse status", () => {
    const { external } = collectBodyRows({
      outers: [
        { partName: "후드", status: "정상" },
        { partName: "후드", status: "교환" },
      ],
      bodyPanels: null,
      bodyChanged: null,
      paintPartTypes: null,
      seriousTypes: null,
      diagnosisItems: null,
    });
    const hood = external.find((r) => r.part === "Капот");
    expect(hood?.status).toBe("Замена");
  });

  it("fills external defaults when only internal damage listed", () => {
    const { external, internal } = collectBodyRows({
      outers: null,
      bodyPanels: null,
      bodyChanged: null,
      paintPartTypes: null,
      seriousTypes: null,
      diagnosisItems: [
        { name: "PILLAR_PANEL_DASH_PANEL_FLOOR_PANEL", resultCode: "REPAIR" },
      ],
    });
    expect(internal.some((r) => r.part.includes("Стойки"))).toBe(true);
    expect(external.some((r) => r.part === "Капот" && r.status === "Оригинал")).toBe(true);
  });
});
