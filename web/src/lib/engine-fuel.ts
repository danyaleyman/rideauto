/** Heuristic aligned with backend `classify_fuel` (market_pricing_shared). */
export function isElectricFuelType(data: Record<string, unknown> | null | undefined): boolean {
  if (!data) return false;
  const raw = String(data.engine_type ?? data.fuel ?? data.engineType ?? "");
  const s = raw.toLowerCase();
  if (s.includes("электро") || s.includes("electric") || s.trim() === "ev") return true;
  if (raw.includes("전기") && !raw.includes("가솔린") && !raw.includes("디젤") && !raw.includes("하이브리드")) {
    return true;
  }
  return false;
}

export function shouldShowImportExciseVatBreakdown(
  data: Record<string, unknown> | null | undefined,
  exciseRub: number | null,
  vatRub: number | null,
): boolean {
  const eps = 0.01;
  if (isElectricFuelType(data)) return true;
  return (exciseRub != null && Math.abs(exciseRub) > eps) || (vatRub != null && Math.abs(vatRub) > eps);
}
