import { describe, expect, it } from "vitest";
import { createT, t } from "./i18n";

describe("t() / createT()", () => {
  it("returns Russian catalog empty title", () => {
    expect(t("catalog.empty.title")).toContain("объявлений");
  });

  it("returns path for unknown key", () => {
    expect(t("missing.path")).toBe("missing.path");
  });

  it("createT(en) returns English", () => {
    expect(createT("en")("catalog.empty.title")).toContain("filters");
  });

  it("interpolates params", () => {
    expect(createT("ru")("catalog.results.vinDedupe", { count: 3 })).toContain("3");
  });
});
