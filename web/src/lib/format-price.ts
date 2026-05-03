/** Подпись, если в объявлении нет расчётной цены. */
export const PRICE_ON_REQUEST_RU = "Цена по запросу";

/** Форматирование цены для UI (избранное, списки). */
export function formatPriceLabel(n: number | null | undefined): string {
  if (n == null || Number.isNaN(n)) return "—";
  try {
    return new Intl.NumberFormat("ru-RU", {
      style: "currency",
      currency: "RUB",
      maximumFractionDigits: 0,
    }).format(n);
  } catch {
    return `${n} ₽`;
  }
}

/** Карточка каталога: явный флаг из API или отсутствие числа. */
export function formatCatalogCardPrice(
  price: number | null | undefined,
  priceOnRequest?: boolean | null,
): string {
  if (priceOnRequest) return PRICE_ON_REQUEST_RU;
  if (price == null || Number.isNaN(price)) return PRICE_ON_REQUEST_RU;
  if (typeof price === "number" && price <= 0) return PRICE_ON_REQUEST_RU;
  return formatPriceLabel(price);
}
