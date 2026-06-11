import type { CatalogUrlState } from "@/lib/catalog-url";
import { toApiSearchParams } from "@/lib/catalog-url";
import { formatPriceLabel } from "@/lib/format-price";

export type PriceBenchmarkStats = {
  n: number;
  p25_rub: number | null;
  median_rub: number | null;
  p75_rub: number | null;
};

export type PriceBenchmarkListing = {
  price_rub: number;
  vs_median_all_pct: number | null;
  vs_median_clean_pct?: number | null;
  band: "below_typical" | "typical" | "above_typical";
};

export type PriceBenchmarkResponse = {
  cohort: {
    market?: "korea" | "china";
    brand?: string | null;
    brands?: string[];
    models?: string[];
    clusters?: string[];
    year_from?: number | null;
    year_to?: number | null;
    mileage_band?: string | null;
  };
  peer_all: PriceBenchmarkStats | null;
  peer_clean: PriceBenchmarkStats | null;
  listing: PriceBenchmarkListing | null;
  min_n: number;
  eligible: boolean;
};

export function catalogBenchmarkEligible(state: CatalogUrlState): boolean {
  return state.marks.length > 0 && (state.models.length > 0 || state.clusters.length > 0);
}

export function toBenchmarkApiParams(state: CatalogUrlState): URLSearchParams {
  const p = toApiSearchParams({ ...state, page: 1 });
  p.delete("per_page");
  p.delete("cursor");
  p.delete("sort");
  p.delete("price_from");
  p.delete("price_to");
  p.delete("q");
  return p;
}

export function toListingBenchmarkParams(carId: string, state?: CatalogUrlState): URLSearchParams {
  const p = state ? toBenchmarkApiParams(state) : new URLSearchParams();
  p.set("car_id", carId);
  return p;
}

export function formatPriceRangeShort(p25: number, p75: number): string {
  return `${formatPriceLabel(p25)} – ${formatPriceLabel(p75)}`;
}
