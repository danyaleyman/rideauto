"use client";

import { useQuery } from "@tanstack/react-query";
import { fetchCatalogPriceBenchmark } from "@/lib/client-api";
import { toListingBenchmarkParams } from "@/lib/catalog-price-benchmark";

const STALE_MS = 5 * 60_000;

export function useCarPriceBenchmarkQuery(carId: string, enabled = true) {
  const params = toListingBenchmarkParams(carId);
  const key = params.toString();
  return useQuery({
    queryKey: ["car", "price-benchmark", key],
    queryFn: ({ signal }) => fetchCatalogPriceBenchmark(params, signal),
    enabled: enabled && Boolean(carId),
    staleTime: STALE_MS,
  });
}
