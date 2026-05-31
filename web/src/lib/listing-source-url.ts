function pickHttpUrl(v: unknown): string | null {
  const s = typeof v === "string" ? v.trim() : "";
  return s.startsWith("http") ? s : null;
}

/** Ссылка на оригинальное объявление на площадке (Encar / Che168). */
export function listingSourceUrl(
  data: Record<string, unknown>,
  carId?: string,
): string | null {
  const direct =
    pickHttpUrl(data.che168_vehicle_url) ??
    pickHttpUrl(data.url);
  if (direct) return direct;

  const source = String(data.source ?? "").trim().toLowerCase();
  const id = (carId ?? "").trim();
  const isChina =
    source === "che168" ||
    source === "china" ||
    id.toLowerCase().startsWith("che168-");
  if (!isChina) return null;

  const innerRaw =
    data.inner_id ??
    data.che168_listing_id ??
    (id.toLowerCase().startsWith("che168-") ? id.slice("che168-".length) : null);
  const inner = innerRaw != null ? String(innerRaw).trim() : "";
  if (!inner) return null;
  return `https://global.che168.com/detail/${encodeURIComponent(inner)}`;
}
