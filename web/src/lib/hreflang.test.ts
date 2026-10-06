import { describe, expect, it } from "vitest";
import { buildLocaleAlternates } from "./hreflang";

describe("buildLocaleAlternates", () => {
  it("uses /en and /ru prefixes and keeps query without lang=", () => {
    const { languages, canonical } = buildLocaleAlternates("/catalog", "?region=korea");
    expect(languages["en-US"]).toContain("/en/catalog");
    expect(languages["en-US"]).toContain("region=korea");
    expect(languages["en-US"]).not.toContain("lang=");
    expect(languages["ru-RU"]).toContain("/ru/catalog");
    expect(canonical).toContain("/ru/catalog");
  });

  it("canonical follows /en prefix when present", () => {
    const { canonical, languages } = buildLocaleAlternates("/en/buy", "");
    expect(canonical).toMatch(/\/en\/buy$/);
    expect(languages["ru-RU"]).toMatch(/\/ru\/buy$/);
  });

  it("normalizes path without double slash", () => {
    const { canonical } = buildLocaleAlternates("/buy", "");
    expect(canonical).toMatch(/\/ru\/buy$/);
  });
});
