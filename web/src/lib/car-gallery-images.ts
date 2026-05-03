import { extractCarImageUrls } from "@/lib/car-images";

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

/** Собирает URL из Encar h_images (поле path), если объекты без готового https. */
function urlsFromEncarHImages(raw: Record<string, unknown>): string[] {
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
  const out: string[] = [];
  for (const item of arr) {
    if (!item || typeof item !== "object") continue;
    const path = (item as { path?: unknown }).path;
    if (typeof path !== "string" || !path.startsWith("/")) continue;
    const slug = path.startsWith("/") ? `carpicture${path}` : `carpicture/${path}`;
    const u = `https://ci.encar.com/${slug}?impolicy=heightRate&rh=696&cw=1160&ch=696&cg=Center`;
    out.push(u);
  }
  return out;
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

/** URL снизу / диагностика в корейском контуре. */
function collectDiagnosisPhotoUrls(raw: Record<string, unknown>): string[] {
  const extra = raw.extra;
  if (!extra || typeof extra !== "object" || Array.isArray(extra)) return [];
  const e = extra as Record<string, unknown>;
  const photos = e.diagnosis_photos;
  if (!Array.isArray(photos)) return [];
  const out: string[] = [];
  for (const u of photos) {
    if (typeof u === "string" && /^https?:\/\//i.test(u)) out.push(u);
  }
  return out;
}

/**
 * Все URL для галереи: обычные фото + диагностика (без дубликатов, стабильный порядок).
 */
export function getAllCarPhotoUrls(data: Record<string, unknown>): string[] {
  const main = extractCarImageUrls(data);
  const fromHi = urlsFromEncarHImages(data);
  const diag = collectDiagnosisPhotoUrls(data);
  const seen = new Set<string>();
  const out: string[] = [];
  for (const u of [...main, ...fromHi, ...diag]) {
    const s = u.trim();
    if (!/^https?:\/\//i.test(s)) continue;
    const key = imageUrlDedupeKey(s);
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(s);
  }
  return out;
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
