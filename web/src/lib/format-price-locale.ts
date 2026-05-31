import { createT, type AppLocale } from "@/lib/i18n";
import { formatPriceLabel } from "@/lib/format-price";

export function priceOnRequestLabel(locale: AppLocale): string {
  return createT(locale)("common.priceOnRequest");
}

export function formatCatalogCardPriceLocale(
  locale: AppLocale,
  price: number | null | undefined,
  priceOnRequest?: boolean | null,
): string {
  if (priceOnRequest) return priceOnRequestLabel(locale);
  if (price == null || Number.isNaN(price)) return priceOnRequestLabel(locale);
  if (typeof price === "number" && price <= 0) return priceOnRequestLabel(locale);
  return formatPriceLabel(price);
}
