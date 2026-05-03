import type { Metadata } from "next";
import { Suspense } from "react";
import { CatalogClient } from "@/components/catalog/CatalogClient";
import { CatalogPageLayout } from "@/components/catalog/CatalogPageLayout";
import {
  catalogStateFromRecord,
  catalogStateKey,
  catalogStateToFetchParams,
} from "@/lib/catalog-url";
import { fetchSearch } from "@/lib/api";
import { emptySearchResponse } from "@/lib/catalog-empty-search";
import type { SearchResponse } from "@/lib/types";

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

export default async function CatalogPage({ searchParams }: PageProps) {
  const sp = await searchParams;
  const state = catalogStateFromRecord(sp);
  const ssrKey = catalogStateKey(state);
  const flat = catalogStateToFetchParams(state);

  let initial: SearchResponse = emptySearchResponse();
  let ssrDegraded = false;
  try {
    initial = await fetchSearch(flat, { revalidate: 30 });
  } catch {
    ssrDegraded = true;
  }

  return (
    <CatalogPageLayout>
      <Suspense
        fallback={<div className="py-12 text-center text-muted-foreground">Загрузка каталога…</div>}
      >
        <CatalogClient initialSearch={initial} ssrKey={ssrKey} ssrDegraded={ssrDegraded} />
      </Suspense>
    </CatalogPageLayout>
  );
}
