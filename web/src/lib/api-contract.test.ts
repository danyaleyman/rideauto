import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { assertSearchResponse, assertSlimCatalogItem } from "@/lib/api-contract";

const FIXTURES = join(
  dirname(fileURLToPath(import.meta.url)),
  "../../../backend/tests/fixtures/api_contract",
);

function loadJson(rel: string): unknown {
  return JSON.parse(readFileSync(join(FIXTURES, rel), "utf-8"));
}

describe("api-contract", () => {
  it("accepts golden slim v2 item from backend fixtures", () => {
    const item = loadJson("v2/slim_item_encar.json");
    assertSlimCatalogItem(item, { requireCatalogUpdatedAt: true });
    expect(item.id).toBe("snap-encar-1");
  });

  it("accepts search envelope built from golden slim item", () => {
    const item = loadJson("v2/slim_item_encar.json");
    const body = {
      result: [item],
      meta: {
        total: 1,
        limit: 10,
        per_page: 10,
        pages: 1,
        offset: 0,
        list_mode: "slim",
        api_version: "v2",
        next_cursor: null,
      },
    };
    assertSearchResponse(body);
  });

  it("rejects search meta without list_mode", () => {
    expect(() =>
      assertSearchResponse({
        result: [],
        meta: { total: 0, limit: 10, per_page: 10, pages: 0, offset: 0 },
      }),
    ).toThrow(/list_mode/);
  });
});
