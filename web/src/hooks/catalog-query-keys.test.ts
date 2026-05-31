import { describe, expect, it } from "vitest";
import { catalogKeys } from "@/hooks/catalog-query-keys";

describe("catalogKeys", () => {
  it("builds stable search keys", () => {
    expect(catalogKeys.search("korea|p1")).toEqual(["catalog", "search", "korea|p1"]);
  });

  it("separates facets and search", () => {
    const k = "china|marks=bmw";
    expect(catalogKeys.search(k)).not.toEqual(catalogKeys.facets(k));
  });

  it("scopes daily by market", () => {
    expect(catalogKeys.dailyAdditions("china")).toEqual(["catalog", "daily", "china"]);
    expect(catalogKeys.dailyAdditions("korea")).not.toEqual(catalogKeys.dailyAdditions("china"));
  });
});
