import { PER_PAGE } from "./catalog-url";
import type { SearchMeta, SearchResponse } from "./types";

/** Пустая выдача при ошибке SSR или до первого ответа API (согласовано с `PER_PAGE` каталога). */
export function emptySearchResponse(): SearchResponse {
  const meta: SearchMeta = {
    total: 0,
    limit: PER_PAGE,
    per_page: PER_PAGE,
    pages: 1,
    offset: 0,
  };
  return { result: [], meta };
}
