"use client";

import Link from "next/link";
import { Fragment } from "react";
import { siteBreadcrumbBarClass } from "@/lib/site-layout";
import type { SearchResponse } from "@/lib/types";
import { useCatalogSearchState } from "@/hooks/use-catalog-search-state";
import { CatalogFiltersAside } from "@/components/catalog/CatalogFiltersAside";
import { CatalogMobileFilters } from "@/components/catalog/CatalogMobileFilters";
import { CatalogResultsPanel } from "@/components/catalog/CatalogResultsPanel";
import { CatalogStatusBanners } from "@/components/catalog/CatalogStatusBanners";
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";

export function CatalogClient({
  initialSearch,
  ssrKey,
  ssrDegraded = false,
}: {
  initialSearch: SearchResponse;
  ssrKey: string;
  ssrDegraded?: boolean;
}) {
  const catalog = useCatalogSearchState({ initialSearch, ssrKey, ssrDegraded });

  return (
    <>
      <div className={siteBreadcrumbBarClass}>
        <Breadcrumb className="min-w-0 flex-1">
          <BreadcrumbList className="flex-wrap gap-x-1 gap-y-1 sm:flex-nowrap">
            {catalog.breadcrumbSegments.map((seg, i) => {
              const last = i === catalog.breadcrumbSegments.length - 1;
              return (
                <Fragment key={`${i}-${seg.label}`}>
                  {i > 0 ? <BreadcrumbSeparator /> : null}
                  <BreadcrumbItem className={last ? "min-w-0 max-w-full" : undefined}>
                    {last ? (
                      <BreadcrumbPage className="line-clamp-2 break-words text-start font-medium [overflow-wrap:anywhere] sm:line-clamp-1">
                        {seg.label}
                      </BreadcrumbPage>
                    ) : seg.href ? (
                      <BreadcrumbLink asChild>
                        <Link href={seg.href}>{seg.label}</Link>
                      </BreadcrumbLink>
                    ) : (
                      <BreadcrumbPage>{seg.label}</BreadcrumbPage>
                    )}
                  </BreadcrumbItem>
                </Fragment>
              );
            })}
          </BreadcrumbList>
        </Breadcrumb>
      </div>

      <CatalogStatusBanners
        online={catalog.online}
        showSsrDegradedNotice={catalog.showSsrDegradedNotice}
        err={catalog.err}
        onRetry={catalog.onRetry}
      />

      <CatalogMobileFilters catalog={catalog} />
      <div className="flex min-w-0 flex-col gap-6 lg:flex-row lg:items-start lg:gap-7">
        <CatalogFiltersAside catalog={catalog} />
        <CatalogResultsPanel catalog={catalog} />
      </div>
    </>
  );
}
