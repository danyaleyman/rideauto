import { describe, expect, it } from "vitest";
import { catalogCardImagePlaceholder } from "@/lib/catalog-card-image";

describe("catalogCardImagePlaceholder", () => {
  it("shows loading when URLs exist but proxy pending", () => {
    expect(catalogCardImagePlaceholder(true)).toBe("Загрузка фото…");
  });

  it("shows empty when no URLs", () => {
    expect(catalogCardImagePlaceholder(false)).toBe("Нет фото");
  });
});
