import { extractCarImageUrls, normalizeEncarPhotoUrl } from "@/lib/car-images";
import { pickCarData } from "@/lib/car-seo";

/** Ключ для дедупликации: один кадр корейского контура часто приходит и в `images`, и в `h_images` с разным query. */
export function imageUrlDedupeKey(url: string): string {
  const t = url.trim();
  try {
    const u = new URL(t);
    const path = u.pathname.replace(/\/+/g, "/").toLowerCase();
    const host = u.hostname.toLowerCase();
    if (host.endsWith("encar.com")) return `encar:${path}`;
    // Китайский CDN: один и тот же path с разными query — разные кадры;
    // дедуп только по path сворачивал всю галерею в одно фото.
    if (
      host.includes("byteimg.com") ||
      host.includes("bytecdn.com") ||
      host.includes("p3-dcd.byteimg") ||
      host.includes("p9-dcd.byteimg") ||
      host.includes("dcarimg.com") ||
      host.includes("dcd-cdn") ||
      host.includes("tos-cn-i-")
    ) {
      return `${host}${path}${u.search}`;
    }
    return `${host}${path}`;
  } catch {
    return t.toLowerCase();
  }
}

function encarFaceRank(blob: string): number {
  const t = blob.toLowerCase();
  if (/(전면|정면|front|앞면)/.test(t)) return 0;
  if (/(측면|side)/.test(t)) return 1;
  if (/(후면|후방|rear|back|뒤쪽)/.test(t)) return 3;
  if (/(interior|inside|cabin|내장|실내|내부)/.test(t)) return 5;
  if (/(diag2|underbody|하부)/.test(t)) return 6;
  return 4;
}

function encarSeqFromPath(path: string): number {
  const m = path.match(/_(\d+)\.(?:jpe?g|png|webp)(?:\?|$)/i);
  if (!m) return 1e9;
  const n = Number(m[1]);
  return Number.isFinite(n) ? n : 1e9;
}

function parseHImages(raw: Record<string, unknown>): Array<{ path: string; rank: number; seq: number }> {
  const rawHi = raw.h_images;
  let arr: unknown[] = [];
  if (Array.isArray(rawHi)) arr = rawHi;
  else if (typeof rawHi === "string" && rawHi.trim()) {
    try {
      const p = JSON.parse(rawHi) as unknown;
      if (Array.isArray(p)) arr = p;
    } catch {
      /* ignore */
    }
  }
  const out: Array<{ path: string; rank: number; seq: number }> = [];
  for (const item of arr) {
    if (!item || typeof item !== "object") continue;
    const o = item as { path?: unknown; type?: unknown; desc?: unknown };
    const path = o.path;
    if (typeof path !== "string" || !path.startsWith("/")) continue;
    const blob = `${o.type ?? ""} ${o.desc ?? ""} ${path}`;
    out.push({ path, rank: encarFaceRank(blob), seq: encarSeqFromPath(path) });
  }
  return out;
}

function encarPathKey(urlOrPath: string): string {
  const t = urlOrPath.trim().toLowerCase();
  try {
    const u = new URL(t);
    return u.pathname.replace(/\/+/g, "/");
  } catch {
    const path = t.startsWith("/") ? t : `/${t.replace(/^carpicture\/?/i, "")}`;
    return path.replace(/\/+/g, "/");
  }
}

/** h_images → полный кадр Encar без wtmk. Лицо раньше кормы. */
function urlsFromEncarHImages(raw: Record<string, unknown>): string[] {
  const items = parseHImages(raw).map((h) => {
    const slug = h.path.startsWith("/") ? `carpicture${h.path}` : `carpicture/${h.path}`;
    return { url: normalizeEncarPhotoUrl(`https://ci.encar.com/${slug}`), rank: h.rank, seq: h.seq, path: h.path };
  });
  items.sort((a, b) => a.rank - b.rank || a.seq - b.seq || a.path.localeCompare(b.path));
  return items.map((x) => x.url);
}

function sortKoreaListingUrls(urls: string[], raw: Record<string, unknown>): string[] {
  const hints = parseHImages(raw);
  if (!hints.length) {
    return [...urls].sort((a, b) => encarSeqFromPath(a) - encarSeqFromPath(b) || a.localeCompare(b));
  }
  const byPath = new Map<string, { rank: number; seq: number }>();
  for (const h of hints) {
    byPath.set(encarPathKey(h.path), { rank: h.rank, seq: h.seq });
    byPath.set(encarPathKey(`carpicture${h.path}`), { rank: h.rank, seq: h.seq });
  }
  const hintFor = (url: string) => {
    const key = encarPathKey(url);
    return byPath.get(key) ?? { rank: 4, seq: encarSeqFromPath(url) };
  };
  return [...urls].sort((a, b) => {
    const ha = hintFor(a);
    const hb = hintFor(b);
    return ha.rank - hb.rank || ha.seq - hb.seq || a.localeCompare(b);
  });
}

function listingIsChina(raw: Record<string, unknown>): boolean {
  const source = String(raw.source ?? "").toLowerCase();
  const id = String(raw.id ?? raw.inner_id ?? "");
  return source.includes("che168") || source.includes("china") || id.startsWith("che168");
}

function listingIsKorea(raw: Record<string, unknown>): boolean {
  if (listingIsChina(raw)) return false;
  const source = String(raw.source ?? "").toLowerCase();
  return source.includes("encar") || source.includes("korea") || source === "";
}

function chinaListingIds(raw: Record<string, unknown>): string[] {
  const keys = ["inner_id", "infoid", "infoId", "carid", "carId", "id", "che168_id"];
  const out: string[] = [];
  for (const k of keys) {
    const v = raw[k];
    if (v == null) continue;
    const s = String(v).trim();
    if (s) out.push(s);
  }
  return out;
}

function isForeignChinaPhoto(url: string, listingIds: string[]): boolean {
  const low = url.toLowerCase();
  if (low.includes("encar.com")) return true;
  if (low.includes("autoimg.cn") && !low.includes("2sc")) return true;
  if (["/seriespic", "/modelpic", "factorypic", "/specimg"].some((tok) => low.includes(tok))) {
    return true;
  }
  const digits = listingIds.map((x) => x.replace(/\D/g, "")).filter((x) => x.length >= 5);
  if (!digits.length) return false;
  for (const m of low.matchAll(/(?:infoid|info_id|carid|car_id)=(\d{5,})/g)) {
    const other = m[1];
    if (!digits.some((d) => d === other || d.endsWith(other) || other.endsWith(d))) return true;
  }
  return false;
}

function filterChinaOwnPhotos(raw: Record<string, unknown>, urls: string[]): string[] {
  const ids = chinaListingIds(raw);
  const filtered = urls.filter((u) => !isForeignChinaPhoto(u, ids));
  return filtered.length ? filtered : urls.filter((u) => !u.toLowerCase().includes("encar.com"));
}

function parseJsonArray(v: unknown): unknown[] {
  if (Array.isArray(v)) return v;
  if (typeof v !== "string" || !v.trim()) return [];
  try {
    const p = JSON.parse(v) as unknown;
    return Array.isArray(p) ? p : [];
  } catch {
    return [];
  }
}

function isPhotoUrl(v: unknown): v is string {
  if (typeof v !== "string") return false;
  const t = v.trim();
  return /^https?:\/\//i.test(t) || t.startsWith("/");
}

/** URL снизу / диагностика в корейском контуре. */
function collectDiagnosisPhotoUrls(raw: Record<string, unknown>): string[] {
  const extra = raw.extra;
  if (!extra || typeof extra !== "object" || Array.isArray(extra)) return [];
  const e = extra as Record<string, unknown>;
  const photos = e.diagnosis_photos;
  if (!Array.isArray(photos)) return [];
  const out: string[] = [];
  for (const u of photos) {
    if (isPhotoUrl(u)) out.push(u.trim());
  }
  return out;
}

/**
 * Все URL для галереи: обычные фото + диагностика (без дубликатов, стабильный порядок).
 */
export function getAllCarPhotoUrls(data: Record<string, unknown>): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  const push = (urls: string[]) => {
    for (const u of urls) {
      const s = normalizeEncarPhotoUrl(u.trim());
      if (!/^https?:\/\//i.test(s) && !s.startsWith("/")) continue;
      const key = imageUrlDedupeKey(s);
      if (seen.has(key)) continue;
      seen.add(key);
      out.push(s);
    }
  };

  if (listingIsChina(data)) {
    const chinaOnly = extractCarImageUrls({ ...data, h_images: undefined });
    push(filterChinaOwnPhotos(data, chinaOnly));
    return out;
  }

  if (listingIsKorea(data)) {
    const listing = extractCarImageUrls(data).map(normalizeEncarPhotoUrl);
    push(sortKoreaListingUrls(listing, data));
    if (!out.length) {
      push(urlsFromEncarHImages(data));
    }
    push(collectDiagnosisPhotoUrls(data));
    return out;
  }

  push(extractCarImageUrls(data));
  push(urlsFromEncarHImages(data));
  push(collectDiagnosisPhotoUrls(data));
  return out;
}

/** GET /api/car → result: объединяем `data` и pickCarData, чтобы images не терялись при read_model. */
export function carPhotoUrlsFromApiResult(raw: Record<string, unknown>): string[] {
  const inner =
    raw.data && typeof raw.data === "object" && !Array.isArray(raw.data)
      ? (raw.data as Record<string, unknown>)
      : {};
  return getAllCarPhotoUrls({ ...inner, ...pickCarData(raw) });
}

/** Мета по h_images (корейский контур): подписи к кадрам для подписей в модалке. */
export function getHImageMeta(data: Record<string, unknown>): Map<string, string> {
  const map = new Map<string, string>();
  const raw = data.h_images;
  const arr = parseJsonArray(raw);
  for (const item of arr) {
    if (!item || typeof item !== "object") continue;
    const o = item as { path?: unknown; desc?: unknown; code?: unknown; type?: unknown };
    const path = typeof o.path === "string" ? o.path : "";
    let urlHint = "";
    if (path && path.startsWith("/")) urlHint = `https://ci.encar.com/carpicture${path}`;
    const desc = [o.desc, o.type, o.code].filter((x) => x != null && String(x).trim()).join(" · ");
    if (urlHint && desc) {
      map.set(urlHint, desc);
      map.set(path, desc);
    }
  }
  return map;
}
