import { describe, expect, it } from "vitest";
import { buildCatalogSeo, catalogIsIndexable } from "@/lib/catalog-seo";
import { catalogStateFromRecord } from "@/lib/catalog-url";

function state(raw: Record<string, string>) {
  return catalogStateFromRecord(raw);
}

describe("buildCatalogSeo", () => {
  it("base korea catalog is indexable with generic title", () => {
    const seo = buildCatalogSeo(state({ region: "korea" }));
    expect(seo.title).toBe("Автомобили из Кореи");
    expect(seo.index).toBe(true);
    expect(seo.description).toContain("из Кореи");
  });

  it("base china catalog uses china label", () => {
    const seo = buildCatalogSeo(state({ region: "china" }));
    expect(seo.title).toBe("Автомобили из Китая");
    expect(seo.index).toBe(true);
  });

  it("single mark is indexable and named", () => {
    const seo = buildCatalogSeo(state({ region: "korea", marks: "BMW" }));
    expect(seo.title).toBe("BMW из Кореи");
    expect(seo.index).toBe(true);
  });

  it("single mark + model is indexable", () => {
    const seo = buildCatalogSeo(state({ region: "korea", marks: "BMW", models: "X5" }));
    expect(seo.title).toBe("BMW X5 из Кореи");
    expect(seo.index).toBe(true);
  });

  it("adds price ceiling to title", () => {
    const seo = buildCatalogSeo(
      state({ region: "korea", marks: "BMW", models: "X5", price_to: "3000000" }),
    );
    expect(seo.title).toContain("BMW X5 из Кореи до");
    expect(seo.title).toContain("₽");
    // ценовой диапазон → не индексируем
    expect(seo.index).toBe(false);
  });

  it("adds year range to title", () => {
    const seo = buildCatalogSeo(
      state({ region: "korea", marks: "BMW", year_from: "2020", year_to: "2023" }),
    );
    expect(seo.title).toContain("2020–2023");
  });

  it("search query yields noindex search title", () => {
    const seo = buildCatalogSeo(state({ region: "korea", q: "tucson" }));
    expect(seo.title).toBe("Поиск: tucson");
    expect(seo.index).toBe(false);
  });

  it("multi-mark is not indexable", () => {
    expect(catalogIsIndexable(state({ region: "korea", marks: "BMW,Audi" }))).toBe(false);
  });

  it("pagination beyond 1 is not indexable", () => {
    expect(catalogIsIndexable(state({ region: "korea", marks: "BMW", page: "2" }))).toBe(false);
  });

  it("model without mark is not indexable", () => {
    expect(catalogIsIndexable(state({ region: "korea", models: "X5" }))).toBe(false);
  });

  it("non-default sort is not indexable", () => {
    expect(catalogIsIndexable(state({ region: "korea", marks: "BMW", sort: "price_low" }))).toBe(
      false,
    );
  });
});
