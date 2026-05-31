import { catalogImageProxyUrl } from "@/lib/catalog-image-proxy";

/** Для скачивания всегда через backend-proxy: прямой fetch к Encar/Che168/CDN даёт CORS «Failed to fetch». */
async function resolveFetchUrl(url: string): Promise<string> {
  const t = url.trim();
  if (!/^https?:\/\//i.test(t)) return t;
  return catalogImageProxyUrl(t, "medium");
}

function extensionFromContentType(ct: string | null, url: string): string {
  if (ct?.includes("png")) return "png";
  if (ct?.includes("webp")) return "webp";
  if (ct?.includes("gif")) return "gif";
  if (ct?.includes("jpeg") || ct?.includes("jpg")) return "jpg";
  try {
    const path = new URL(url).pathname.toLowerCase();
    const m = /\.(jpe?g|png|webp|gif)$/.exec(path);
    if (m) return m[1] === "jpeg" ? "jpg" : m[1];
  } catch {
    /* ignore */
  }
  return "jpg";
}

function triggerBlobDownload(blob: Blob, filename: string) {
  const objectUrl = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = objectUrl;
  a.download = filename;
  a.rel = "noopener";
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.setTimeout(() => URL.revokeObjectURL(objectUrl), 4000);
}

/** Скачивает все фото карточки по одному файлу (с учётом image proxy). */
export async function downloadCarPhotos(
  photoUrls: string[],
  carId: string,
  onProgress?: (done: number, total: number) => void,
): Promise<void> {
  const list = photoUrls.map((u) => u.trim()).filter((u) => /^https?:\/\//i.test(u));
  if (!list.length) throw new Error("Нет фотографий для скачивания");

  for (let i = 0; i < list.length; i++) {
    const raw = list[i];
    const fetchUrl = await resolveFetchUrl(raw);
    let res: Response;
    try {
      res = await fetch(fetchUrl, { credentials: "same-origin", cache: "no-store" });
    } catch {
      throw new Error(`Сеть: не удалось загрузить фото ${i + 1}`);
    }
    if (!res.ok) throw new Error(`Сервер ${res.status}: фото ${i + 1}`);
    const blob = await res.blob();
    const ext = extensionFromContentType(res.headers.get("content-type"), raw);
    triggerBlobDownload(blob, `rideauto-${carId}-${String(i + 1).padStart(2, "0")}.${ext}`);
    onProgress?.(i + 1, list.length);
    if (i < list.length - 1) {
      await new Promise((r) => window.setTimeout(r, 280));
    }
  }
}
