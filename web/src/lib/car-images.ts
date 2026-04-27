function parseJsonMaybe(v: unknown): unknown {
  if (typeof v !== "string") return v;
  try {
    return JSON.parse(v);
  } catch {
    return v;
  }
}

/** Иногда `images` приходит строкой JSON; редко — двойная сериализация. */
function unwrapJsonStrings(v: unknown, depth = 0): unknown {
  if (depth > 6) return v;
  if (typeof v !== "string") return v;
  const s = v.trim();
  if (!s) return v;
  try {
    const p = JSON.parse(s) as unknown;
    if (typeof p === "string") return unwrapJsonStrings(p, depth + 1);
    return p;
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
    s.includes("watermark") ||
    s.includes("poster") ||
    s.includes("banner") ||
    s.includes("ad_") ||
    s.includes("icon_") ||
    s.includes("logo")
  );
}

function collectRawImageUrls(raw: Record<string, unknown>): string[] {
  const fields: unknown[] = [
    raw.cover,
    raw.cover_image,
    raw.coverImage,
    raw.main_image,
    raw.mainImage,
    raw.image,
    raw.img,
    raw.photo,
    raw.images,
    raw.h_images,
  ];
  const out: string[] = [];
  for (const field of fields) {
    const value = unwrapJsonStrings(parseJsonMaybe(field));
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
      const o = item as Record<string, unknown>;
      const maybeUrl =
        o.url ??
        o.imageUrl ??
        o.src ??
        o.image ??
        o.pic_url ??
        o.picUrl ??
        o.big_url ??
        o.bigUrl ??
        o.thumb_url ??
        o.thumbUrl ??
        o.cover_url ??
        o.coverUrl;
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
