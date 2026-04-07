"use client";

import { useEffect } from "react";

const SCRIPTS = ["/js/header-init.js?v=20260410", "/js/cookie-consent.js?v=20260421"];

function appendScript(src: string): Promise<void> {
  const existing = document.querySelector(`script[src="${src}"]`);
  if (existing) return Promise.resolve();
  return new Promise((resolve, reject) => {
    const el = document.createElement("script");
    el.src = src;
    el.defer = true;
    el.onload = () => resolve();
    el.onerror = () => reject(new Error(`script ${src}`));
    document.body.appendChild(el);
  });
}

export function LegacyMarketingScripts() {
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        for (const src of SCRIPTS) {
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
  }, []);
  return null;
}
