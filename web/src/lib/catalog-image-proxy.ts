"use client";

import { useEffect, useMemo, useRef, useState } from "react";

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

function thumbPlaceholderRow(list: string[]): string[] {
  return list.map((u) => (catalogImageNeedsProxy(u) ? "" : u));
}

export function useProxiedCatalogThumbUrls(urls: string[]): string[] {
  const [out, setOut] = useState(() => thumbPlaceholderRow(urls));
  const urlsRef = useRef(urls);
  urlsRef.current = urls;
  const key = urls.join("\n");
  useEffect(() => {
    const list = urlsRef.current;
    if (!list.length) {
      setOut([]);
      return;
    }
    if (!list.some(catalogImageNeedsProxy)) {
      setOut(list);
      return;
    }
    setOut(thumbPlaceholderRow(list));
    let cancelled = false;
    void (async () => {
      const next = await Promise.all(
        list.map((u) => (catalogImageNeedsProxy(u) ? catalogImageProxyUrl(u, "thumb") : Promise.resolve(u))),
      );
      if (!cancelled) setOut(next);
    })();
    return () => {
      cancelled = true;
    };
  }, [key]);
  return out;
}

/**
 * Одна асинхронная фаза на страницу каталога: дедуп SHA-256 по уникальным URL,
 * вместо N хуков по карточкам (Китай / прокси).
 */
export function useBatchProxiedCatalogThumbUrls(
  rows: readonly { key: string; urls: string[] }[],
): ReadonlyMap<string, string[]> {
  const rowsRef = useRef(rows);
  rowsRef.current = rows;
  const stableKey = useMemo(
    () => rows.map((r) => `${r.key}\n${r.urls.join("\n")}`).join("\n\u0001\n"),
    [rows],
  );

  const baseMap = useMemo(() => {
    const m = new Map<string, string[]>();
    for (const r of rows) m.set(r.key, thumbPlaceholderRow([...r.urls]));
    return m;
  }, [rows]);

  const [resolvedMap, setResolvedMap] = useState<Map<string, string[]> | null>(null);

  useEffect(() => {
    setResolvedMap(null);
    const current = rowsRef.current;
    const needsProxy = current.some((r) => r.urls.some(catalogImageNeedsProxy));
    if (!needsProxy) return;

    let cancelled = false;
    void (async () => {
      const uniqueProxied = new Map<string, string>();
      const rawNeeding = new Set<string>();
      for (const r of current) {
        for (const u of r.urls) {
          if (catalogImageNeedsProxy(u)) rawNeeding.add(u.trim());
        }
      }
      await Promise.all(
        [...rawNeeding].map(async (raw) => {
          uniqueProxied.set(raw, await catalogImageProxyUrl(raw, "thumb"));
        }),
      );
      if (cancelled) return;
      const next = new Map<string, string[]>();
      for (const r of current) {
        next.set(
          r.key,
          r.urls.map((u) => {
            const t = u.trim();
            return catalogImageNeedsProxy(u) ? (uniqueProxied.get(t) ?? u) : u;
          }),
        );
      }
      setResolvedMap(next);
    })();
    return () => {
      cancelled = true;
    };
  }, [stableKey]);

  return resolvedMap ?? baseMap;
}

export function useProxiedCarGalleryUrls(urls: string[]): { thumbUrls: string[]; mediumUrls: string[] } {
  const galleryPlaceholder = (list: string[]) => list.map((u) => (catalogImageNeedsProxy(u) ? "" : u));
  const [thumbUrls, setThumbUrls] = useState(() => galleryPlaceholder(urls));
  const [mediumUrls, setMediumUrls] = useState(() => galleryPlaceholder(urls));
  const urlsRef = useRef(urls);
  urlsRef.current = urls;
  const key = urls.join("\n");
  useEffect(() => {
    const list = urlsRef.current;
    if (!list.length) {
      setThumbUrls([]);
      setMediumUrls([]);
      return;
    }
    if (!list.some(catalogImageNeedsProxy)) {
      setThumbUrls(list);
      setMediumUrls(list);
      return;
    }
    const pending = galleryPlaceholder(list);
    setThumbUrls(pending);
    setMediumUrls(pending);
    let cancelled = false;
    void (async () => {
      const t = await Promise.all(
        list.map((u) => (catalogImageNeedsProxy(u) ? catalogImageProxyUrl(u, "thumb") : Promise.resolve(u))),
      );
      const m = await Promise.all(
        list.map((u) => (catalogImageNeedsProxy(u) ? catalogImageProxyUrl(u, "medium") : Promise.resolve(u))),
      );
      if (!cancelled) {
        setThumbUrls(t);
        setMediumUrls(m);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [key]);
  return { thumbUrls, mediumUrls };
}
