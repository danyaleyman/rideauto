import type { Metadata } from "next";
import { Suspense } from "react";
import { CatalogClient } from "@/components/catalog/CatalogClient";
import {
  catalogStateFromRecord,
  catalogStateKey,
  catalogStateToFetchParams,
} from "@/lib/catalog-url";
import { fetchSearch } from "@/lib/api";
import type { SearchMeta, SearchResponse } from "@/lib/types";

type PageProps = {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
};

export async function generateMetadata({
  searchParams,
}: PageProps): Promise<Metadata> {
  const sp = await searchParams;
  const q = typeof sp.q === "string" ? sp.q.trim() : "";
  const title = q ? `Поиск: ${q}` : "Каталог";
  return {
    title,
    description:
      "Автомобили из Кореи и Китая: фильтры и поиск через Meilisearch, карточки из PostgreSQL.",
  };
}

function emptySearch(): SearchResponse {
  const meta: SearchMeta = {
    total: 0,
    limit: 12,
    per_page: 12,
    pages: 1,
    offset: 0,
  };
  return { result: [], meta };
}

export default async function CatalogPage({ searchParams }: PageProps) {
  const sp = await searchParams;
  const state = catalogStateFromRecord(sp);
  const ssrKey = catalogStateKey(state);
  const flat = catalogStateToFetchParams(state);

  let initial: SearchResponse;
  try {
    initial = await fetchSearch(flat, { revalidate: 30 });
  } catch {
    initial = emptySearch();
  }

  return (
    <Suspense
      fallback={
        <div className="mx-auto max-w-7xl px-4 py-16 text-center text-zinc-500">
          Загрузка каталога…
        </div>
      }
    >
      <CatalogClient initialSearch={initial} ssrKey={ssrKey} />
    </Suspense>
  );
}
