"use client";

import { useVirtualizer } from "@tanstack/react-virtual";
import type { CatalogSearchController } from "@/hooks/use-catalog-search-state";
import { CatalogListingCard } from "@/components/catalog/CatalogListingCard";
import { previewImageUrls } from "@/lib/catalog-client-utils";
import type { SlimCar } from "@/lib/types";
import { cn } from "@/lib/utils";

/** Высота ряда md:flex-row (~288px превью + текст); занижение + overflow-hidden на Card обрезало карточки. */
const ESTIMATE_ROW_PX = 360;
const OVERSCAN = 5;

export function CatalogVirtualResultsList({
  catalog,
  cars,
  className,
}: {
  catalog: CatalogSearchController;
  cars: SlimCar[];
  className?: string;
}) {
  const { resultsListRef, catalogGridThumbRows, proxiedCatalogThumbsByCar } = catalog;

  const virtualizer = useVirtualizer({
    count: cars.length,
    getScrollElement: () =>
      typeof document !== "undefined" ? document.documentElement : null,
    estimateSize: () => ESTIMATE_ROW_PX,
    overscan: OVERSCAN,
  });

  const items = virtualizer.getVirtualItems();

  return (
    <ul
      ref={resultsListRef}
      className={cn("relative flex scroll-mt-28 flex-col md:scroll-mt-32", className)}
      style={{ height: virtualizer.getTotalSize() }}
    >
      {items.map((virtualRow) => {
        const car = cars[virtualRow.index];
        if (!car) return null;
        return (
          <li
            key={car.id}
            data-index={virtualRow.index}
            ref={virtualizer.measureElement}
            className="absolute start-0 top-0 w-full pb-3"
            style={{ transform: `translateY(${virtualRow.start}px)` }}
          >
            <CatalogListingCard
              catalog={catalog}
              car={car}
              idx={virtualRow.index}
              preview={
                proxiedCatalogThumbsByCar.get(car.id)?.urls ??
                catalogGridThumbRows[virtualRow.index]?.urls ??
                previewImageUrls(car)
              }
            />
          </li>
        );
      })}
    </ul>
  );
}
