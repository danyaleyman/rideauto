import type { Metadata } from "next";
import { Suspense } from "react";
import { CatalogClient } from "@/components/catalog/CatalogClient";
import { CatalogPageLayout } from "@/components/catalog/CatalogPageLayout";
import {
  catalogStateFromRecord,
  catalogStateKey,
  catalogStateToFetchParams,
} from "@/lib/catalog-url";
import { buildCatalogSeo } from "@/lib/catalog-seo";
import { createT } from "@/lib/i18n";
import { getServerLocale } from "@/lib/locale-server";
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
  const state = catalogStateFromRecord(sp);
  const locale = await getServerLocale();
  const seo = buildCatalogSeo(state, locale);
  return {
    title: seo.title,
    description: seo.description,
    robots: seo.index ? undefined : { index: false, follow: true },
  };
}

export default async function CatalogPage({ searchParams }: PageProps) {
  const sp = await searchParams;
  const state = catalogStateFromRecord(sp);
  const ssrKey = catalogStateKey(state);
  const flat = catalogStateToFetchParams(state);

  const locale = await getServerLocale();
  const t = createT(locale);

  let initial: SearchResponse = emptySearchResponse();
  let ssrDegraded = false;
  try {
    initial = await fetchSearch(flat, { revalidate: 30 });
  } catch (e) {
    console.error(
      "[rideauto] catalog SSR fetchSearch failed (client will retry via /api). Check api logs and WRA_API_INTERNAL on web:",
      e instanceof Error ? e.message : e,
    );
    ssrDegraded = true;
  }

  return (
    <CatalogPageLayout>
      <Suspense
        fallback={<div className="py-12 text-center text-muted-foreground">{t("catalog.error.ssrLoading")}</div>}
      >
        <CatalogClient initialSearch={initial} ssrKey={ssrKey} ssrDegraded={ssrDegraded} />
      </Suspense>
    </CatalogPageLayout>
  );
}
