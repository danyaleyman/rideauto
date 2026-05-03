import { describe, expect, it } from "vitest";
import {
  catalogStateFromRecord,
  catalogStateKey,
  parseCatalogUrl,
  PER_PAGE,
  stateToBrowserUrl,
  toApiSearchParams,
} from "./catalog-url";
import { encodeOffsetCursor } from "./cursor";

describe("parseCatalogUrl", () => {
  it("defaults to Korea / encar", () => {
    const s = parseCatalogUrl(new URLSearchParams());
    expect(s.market).toBe("korea");
  });

  it("detects China from region", () => {
    const s = parseCatalogUrl(new URLSearchParams("region=china"));
    expect(s.market).toBe("china");
  });

  it("reads q and query alias", () => {
    expect(parseCatalogUrl(new URLSearchParams("q=Kia")).q).toBe("Kia");
    expect(parseCatalogUrl(new URLSearchParams("query=Kia")).q).toBe("Kia");
  });

  it("parses CSV marks and boolean flags", () => {
    const s = parseCatalogUrl(
      new URLSearchParams("marks=Hyundai,Kia&passable_only=1&pricing_tier=full_customs"),
    );
    expect(s.marks).toEqual(["Hyundai", "Kia"]);
    expect(s.passable_only).toBe(true);
    expect(s.pricing_tier).toBe("full_customs");
  });

  it("maps cursor to page when limit matches PER_PAGE", () => {
    const sp = new URLSearchParams();
    sp.set("cursor", encodeOffsetCursor(PER_PAGE, PER_PAGE));
    const s = parseCatalogUrl(sp);
    expect(s.page).toBe(2);
  });
});

describe("stateToBrowserUrl", () => {
  it("sorts keys for stable catalogStateKey", () => {
    const a = catalogStateFromRecord({ q: "z", marks: "B,A", region: "korea" });
    const b = catalogStateFromRecord({ marks: "B,A", region: "korea", q: "z" });
    expect(catalogStateKey(a)).toBe(catalogStateKey(b));
    expect(stateToBrowserUrl(a)).toMatch(/marks=/);
    expect(stateToBrowserUrl(a)).toMatch(/region=korea/);
  });
});

describe("toApiSearchParams", () => {
  it("sets per_page and encodes cursor for page > 1", () => {
    const p = toApiSearchParams(
      catalogStateFromRecord({ region: "korea", page: "2" }),
    );
    expect(p.get("per_page")).toBe(String(PER_PAGE));
    expect(p.get("cursor")).toBeTruthy();
  });
});
