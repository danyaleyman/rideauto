"use client";

import { useEffect, useState } from "react";

export type GalleryImageSize = "thumb" | "medium";

export async function sha256HexUtf8(text: string): Promise<string> {
  const data = new TextEncoder().encode(text.trim());
  const hash = await crypto.subtle.digest("SHA-256", data);
  return Array.from(new Uint8Array(hash), (b) => b.toString(16).padStart(2, "0")).join("");
}

/** CDN / листинги Китая: прямой hotlink в браузере часто даёт 403; грузим через /api/images. */
export function catalogImageNeedsProxy(url: string): boolean {
  const u = url.trim();
  if (!/^https?:\/\//i.test(u)) return false;
  try {
    const h = new URL(u).hostname.toLowerCase();
    if (h === "encar.com" || h.endsWith(".encar.com")) return false;
    if (h.endsWith(".autoimg.cn") || h === "autoimg.cn") return true;
    if (h.endsWith(".che168.com") || h === "che168.com") return true;
    if (h.includes("byteimg") || h.includes("bytecdn") || h.includes("dcarimg")) return true;
    return false;
  } catch {
    return false;
  }
}

export async function catalogImageProxyUrl(url: string, size: GalleryImageSize): Promise<string> {
  const raw = url.trim();
  const digest = await sha256HexUtf8(raw);
  return `/api/images/${digest}?size=${size}&src=${encodeURIComponent(raw)}`;
}

export function useProxiedCatalogThumbUrls(urls: string[]): string[] {
  const [out, setOut] = useState(urls);
  const key = urls.join("\n");
  useEffect(() => {
    setOut(urls);
    if (!urls.length || !urls.some(catalogImageNeedsProxy)) return;
    let cancelled = false;
    void (async () => {
      const next = await Promise.all(
        urls.map((u) => (catalogImageNeedsProxy(u) ? catalogImageProxyUrl(u, "thumb") : Promise.resolve(u))),
      );
      if (!cancelled) setOut(next);
    })();
    return () => {
      cancelled = true;
    };
  }, [key, urls]);
  return out;
}

export function useProxiedCarGalleryUrls(urls: string[]): { thumbUrls: string[]; mediumUrls: string[] } {
  const [thumbUrls, setThumbUrls] = useState(urls);
  const [mediumUrls, setMediumUrls] = useState(urls);
  const key = urls.join("\n");
  useEffect(() => {
    setThumbUrls(urls);
    setMediumUrls(urls);
    if (!urls.length || !urls.some(catalogImageNeedsProxy)) return;
    let cancelled = false;
    void (async () => {
      const t = await Promise.all(
        urls.map((u) => (catalogImageNeedsProxy(u) ? catalogImageProxyUrl(u, "thumb") : Promise.resolve(u))),
      );
      const m = await Promise.all(
        urls.map((u) => (catalogImageNeedsProxy(u) ? catalogImageProxyUrl(u, "medium") : Promise.resolve(u))),
      );
      if (!cancelled) {
        setThumbUrls(t);
        setMediumUrls(m);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [key, urls]);
  return { thumbUrls, mediumUrls };
}
