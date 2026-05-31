import { describe, expect, it } from "vitest";
import {
  classifyChinaOptionGroup,
  displayChinaOptionRu,
  isChinaOptionNoise,
} from "@/lib/china-options-display";

describe("displayChinaOptionRu", () => {
  it("expands safety abbreviations", () => {
    expect(displayChinaOptionRu("ABS")).toContain("ABS");
    expect(displayChinaOptionRu("ABS")).toContain("антиблокировоч");
    expect(displayChinaOptionRu("ESP")).toContain("ESP");
    expect(displayChinaOptionRu("Brake Force Distribution EBD/CBC")).toContain("EBD/CBC");
  });

  it("translates lane keeping without broken partial replace", () => {
    expect(displayChinaOptionRu("Lane Keeping Assist System")).toBe("Удержание в полосе");
  });

  it("filters category headers and field labels", () => {
    expect(displayChinaOptionRu("Driving & Handling")).toBe("");
    expect(displayChinaOptionRu("Wheel Rim Material")).toBe("");
    expect(displayChinaOptionRu("Sport")).toBe("");
    expect(isChinaOptionNoise("成功")).toBe(true);
  });

  it("translates multimedia options", () => {
    expect(displayChinaOptionRu("Supports CarPlay")).toBe("Apple CarPlay");
    expect(displayChinaOptionRu("Navigation Traffic Display")).toContain("Навигация");
  });
});

describe("classifyChinaOptionGroup", () => {
  it("classifies by english raw when label is russian", () => {
    expect(classifyChinaOptionGroup("Удержание в полосе", "Lane Keeping Assist System")).toBe("assist");
    expect(classifyChinaOptionGroup("ABS (антиблокировочная система торможения)", "ABS")).toBe("safety");
    expect(classifyChinaOptionGroup("Apple CarPlay", "Supports CarPlay")).toBe("media");
    expect(
      classifyChinaOptionGroup("Память положения электропривода багажника", "Power Tailgate Position Memory"),
    ).toBe("comfort");
  });
});
