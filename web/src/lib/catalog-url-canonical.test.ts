import { describe, expect, it } from "vitest";
import {
  canonicalCatalogQueryString,
  catalogLegacyPathRedirect,
  catalogUrlNeedsCanonicalization,
} from "@/lib/catalog-url-canonical";

describe("catalogUrlNeedsCanonicalization", () => {
  it("flags legacy source param", () => {
    expect(catalogUrlNeedsCanonicalization(new URLSearchParams("source=encar"))).toBe(true);
  });

  it("flags region=korea as redundant", () => {
    expect(catalogUrlNeedsCanonicalization(new URLSearchParams("region=korea&marks=BMW"))).toBe(
      true,
    );
  });
});

describe("canonicalCatalogQueryString", () => {
  it("strips source and encar region", () => {
    expect(canonicalCatalogQueryString(new URLSearchParams("source=encar&marks=BMW"))).toBe(
      "marks=BMW",
    );
  });

  it("keeps china region", () => {
    expect(canonicalCatalogQueryString(new URLSearchParams("source=che168"))).toBe("region=china");
  });
});

describe("catalogLegacyPathRedirect", () => {
  it("maps /catalog/encar to korea", () => {
    expect(catalogLegacyPathRedirect("/catalog/encar")?.market).toBe("korea");
  });

  it("maps /catalog/che168 to china", () => {
    expect(catalogLegacyPathRedirect("/catalog/che168")?.market).toBe("china");
  });
});
