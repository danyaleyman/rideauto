import { describe, expect, it } from "vitest";
import { t } from "./i18n";

describe("t()", () => {
  it("returns Russian catalog empty title", () => {
    expect(t("catalog.empty.title")).toContain("объявлений");
  });

  it("returns path for unknown key", () => {
    expect(t("missing.path")).toBe("missing.path");
  });
});
