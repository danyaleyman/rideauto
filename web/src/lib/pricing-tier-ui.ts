/** Нормализация слоя цены Encar из API (корень или ``pricing_clean``). */
export function extractPricingTier(data: Record<string, unknown>): string | null {
  const direct = data.pricing_tier;
  if (typeof direct === "string" && direct.trim()) return direct.trim();
  const pc = data.pricing_clean;
  if (pc && typeof pc === "object" && !Array.isArray(pc)) {
    const t = (pc as Record<string, unknown>).pricing_tier;
    if (typeof t === "string" && t.trim()) return t.trim();
  }
  return null;
}
