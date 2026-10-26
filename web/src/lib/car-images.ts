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

function isResolvableImageUrl(v: unknown): v is string {
  if (typeof v !== "string") return false;
  const t = v.trim();
  return /^https?:\/\//i.test(t) || t.startsWith("/");
}

function isHttpUrl(v: unknown): v is string {
  return isResolvableImageUrl(v);
}

/**
 * Encar: голый jpg = превью 640×480 с крупным encar.com.
 * heightRate+wtmk = кроп и штамп. widthRate rw=1920 = исходный кадр без штампа.
 */
export function normalizeEncarPhotoUrl(url: string): string {
  const t = url.trim();
  if (!t) return t;
  try {
    const u = new URL(t.startsWith("//") ? `https:${t}` : t);
    if (!u.hostname.toLowerCase().endsWith("encar.com")) return t;
    if (!u.pathname.toLowerCase().includes("carpicture")) return t;
    u.search = "";
    u.hash = "";
    u.searchParams.set("impolicy", "widthRate");
    u.searchParams.set("rw", "1920");
    return u.toString();
  } catch {
    return t;
  }
}

function normalizeImageUrl(v: string): string {
  const t = v.trim();
  if (!t) return t;
  const withProto = t.startsWith("//") ? `https:${t}` : t;
  const safe = withProto.replace(/ /g, "%20");
  if (!/^https?:\/\//i.test(safe)) return safe;
  try {
    const u = new URL(safe);
    // Avoid mixed content on https storefronts: known CDNs support https.
    if (u.protocol === "http:") u.protocol = "https:";
    return normalizeEncarPhotoUrl(u.toString());
  } catch {
    return safe;
  }
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
      out.push(normalizeImageUrl(value));
      continue;
    }
    if (!Array.isArray(value)) continue;
    for (const item of value) {
      if (Array.isArray(item)) {
        for (const nested of item) {
          if (isHttpUrl(nested)) out.push(normalizeImageUrl(nested));
        }
        continue;
      }
      if (isHttpUrl(item)) {
        out.push(normalizeImageUrl(item));
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
      if (isHttpUrl(maybeUrl)) out.push(normalizeImageUrl(maybeUrl));
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
