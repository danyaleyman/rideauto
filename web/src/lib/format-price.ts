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
