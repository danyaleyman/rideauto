import { describe, expect, it } from "vitest";
import { buildLocaleAlternates } from "./hreflang";

describe("buildLocaleAlternates", () => {
  it("adds lang=en for en-US and strips for ru", () => {
    const { languages } = buildLocaleAlternates("/catalog", "?region=korea");
    expect(languages["en-US"]).toContain("lang=en");
    expect(languages["ru-RU"]).not.toContain("lang=");
    expect(languages["ru-RU"]).toContain("region=korea");
  });

  it("normalizes path without double slash", () => {
    const { canonical } = buildLocaleAlternates("/buy", "");
    expect(canonical).toMatch(/\/buy$/);
  });
});
