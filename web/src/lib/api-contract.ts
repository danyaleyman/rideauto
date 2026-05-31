/**
 * Валидация тел ответов каталога (зеркало backend `catalog_contract.py` для фронта).
 */
import type { SearchResponse, SlimCar } from "@/lib/types";

const SLIM_REQUIRED = new Set([
  "id",
  "title",
  "data",
  "read_model",
  "price",
  "price_on_request",
  "year_num",
  "api_contract_version",
]);

export function assertSlimCatalogItem(
  item: unknown,
  opts?: { requireCatalogUpdatedAt?: boolean },
): asserts item is SlimCar {
  if (!item || typeof item !== "object") {
    throw new Error("slim item must be an object");
  }
  const row = item as Record<string, unknown>;
  const missing = [...SLIM_REQUIRED].filter((k) => !(k in row));
  if (missing.length) {
    throw new Error(`slim item missing keys: ${missing.join(", ")}`);
  }
  if (typeof row.id !== "string" || !row.id.trim()) {
    throw new Error("slim item.id must be a non-empty string");
  }
  if (!row.data || typeof row.data !== "object") {
    throw new Error("slim item.data must be an object");
  }
  if (!row.read_model || typeof row.read_model !== "object") {
    throw new Error("slim item.read_model must be an object");
  }
  if (opts?.requireCatalogUpdatedAt) {
    const ts = row.catalog_updated_at;
    if (typeof ts !== "string" || !ts.trim()) {
      throw new Error("slim item requires catalog_updated_at (API v2)");
    }
  }
}

export function assertSearchResponse(body: unknown): asserts body is SearchResponse {
  if (!body || typeof body !== "object") {
    throw new Error("search body must be an object");
  }
  const envelope = body as Record<string, unknown>;
  const meta = envelope.meta;
  if (!meta || typeof meta !== "object") {
    throw new Error("search response missing meta");
  }
  const m = meta as Record<string, unknown>;
  for (const key of ["total", "limit", "per_page", "pages", "offset"] as const) {
    if (typeof m[key] !== "number" || !Number.isFinite(m[key])) {
      throw new Error(`search meta.${key} must be a number`);
    }
  }
  if (typeof m.list_mode !== "string" || !m.list_mode.trim()) {
    throw new Error("search meta.list_mode must be a string");
  }
  const apiVer = String(m.api_version ?? "v1")
    .trim()
    .toLowerCase();
  const requireTs = apiVer === "v2";
  const result = envelope.result;
  if (!Array.isArray(result)) {
    throw new Error("search result must be an array");
  }
  const mode = String(m.list_mode).trim().toLowerCase();
  if (mode === "slim") {
    for (let i = 0; i < result.length; i++) {
      try {
        assertSlimCatalogItem(result[i], { requireCatalogUpdatedAt: requireTs });
      } catch (e) {
        throw new Error(`search slim item ${i}: ${e instanceof Error ? e.message : String(e)}`);
      }
    }
  }
}
