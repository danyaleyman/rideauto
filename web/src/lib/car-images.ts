function parseJsonMaybe(v: unknown): unknown {
  if (typeof v !== "string") return v;
  try {
    return JSON.parse(v);
  } catch {
    return v;
  }
}

function isHttpUrl(v: unknown): v is string {
  return typeof v === "string" && /^https?:\/\//i.test(v);
}

function isLikelyNonPhoto(url: string): boolean {
  const s = url.toLowerCase();
  return (
    s.includes("/motor-mis-img/") ||
    s.includes("tplv-dcdx-default") ||
    s.includes("tplv-dcdx-sh-1.png") ||
    s.includes("tplv-dcdx-sh-1.") ||
    s.includes("/img/tos-cn-i-dcdx/") ||
    (s.includes("/tos-cn-i-dcdx/") && s.includes(".png")) ||
    s.includes("watermark") ||
    s.includes("poster") ||
    s.includes("banner") ||
    s.includes("ad_") ||
    s.includes("icon_") ||
    s.includes("logo") ||
    s.includes("icon")
  );
}

function collectRawImageUrls(raw: Record<string, unknown>): string[] {
  const fields: unknown[] = [raw.image, raw.img, raw.photo, raw.images, raw.h_images];
  const out: string[] = [];
  for (const field of fields) {
    const value = parseJsonMaybe(field);
    if (isHttpUrl(value)) {
      out.push(value);
      continue;
    }
    if (!Array.isArray(value)) continue;
    for (const item of value) {
      if (isHttpUrl(item)) {
        out.push(item);
        continue;
      }
      if (!item || typeof item !== "object") continue;
      const maybeUrl =
        (item as { url?: unknown; imageUrl?: unknown; src?: unknown }).url ??
        (item as { url?: unknown; imageUrl?: unknown; src?: unknown }).imageUrl ??
        (item as { url?: unknown; imageUrl?: unknown; src?: unknown }).src;
      if (isHttpUrl(maybeUrl)) out.push(maybeUrl);
    }
  }
  return Array.from(new Set(out));
}

export function extractCarImageUrls(raw: Record<string, unknown>): string[] {
  const all = collectRawImageUrls(raw);
  const filtered = all.filter((u) => !isLikelyNonPhoto(u));
  // Never return empty if source had images.
  return filtered.length ? filtered : all;
}
