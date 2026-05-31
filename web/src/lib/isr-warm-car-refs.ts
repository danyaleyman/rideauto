/**
 * ID карточек для on-demand ISR warm (env или статический список).
 * `WRA_ISR_WARM_CAR_REFS=id1,id2` — через запятую, макс. 24.
 */
export function getIsrWarmCarRefs(): string[] {
  const raw = process.env.WRA_ISR_WARM_CAR_REFS?.trim();
  if (!raw) return [];
  return raw
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean)
    .slice(0, 24);
}
