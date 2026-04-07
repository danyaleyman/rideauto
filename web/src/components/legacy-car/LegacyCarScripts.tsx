"use client";

import { useEffect } from "react";

const CHAIN = [
  "/js/wra-site-config.js?v=20260421",
  "/js/copy-protection.js",
  "/js/auth-favorites.js?v=20260422",
  "/js/wra-analytics.js?v=20260423",
  "/js/wra-context-bar.js?v=20260423",
  "/js/car-page-dicts.js?v=20260405car",
  "/js/car-page.js?v=20260422car",
  "/js/header-init.js",
  "/js/cookie-consent.js?v=20260421",
] as const;

function appendScript(src: string): Promise<void> {
  const existing = document.querySelector(`script[src="${src}"]`);
  if (existing) return Promise.resolve();
  return new Promise((resolve, reject) => {
    const el = document.createElement("script");
    el.src = src;
    el.async = false;
    el.onload = () => resolve();
    el.onerror = () =>
      reject(new Error(`[LegacyCarScripts] failed to load ${src}`));
    document.body.appendChild(el);
  });
}

export function LegacyCarScripts({ carRef }: { carRef: string }) {
  useEffect(() => {
    let cancelled = false;

    (async () => {
      try {
        if (typeof window !== "undefined") {
          window.__WRA_NEXT_CAR_ID__ = carRef;
          window.WRA_USE_NEXT_CAR_ROUTES = true;
        }
        for (const src of CHAIN) {
          if (cancelled) return;
          await appendScript(src);
        }
      } catch (e) {
        console.error(e);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [carRef]);

  return null;
}
