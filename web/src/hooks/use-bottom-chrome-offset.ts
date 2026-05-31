"use client";

import { useEffect, useState } from "react";
import { COOKIE_CONSENT_EVENT } from "@/lib/cookie-consent";

/** Высота нижних fixed-баров (cookie) для сдвига sticky CTA. */
export function useBottomChromeOffset() {
  const [cookiePx, setCookiePx] = useState(0);

  useEffect(() => {
    const read = () => {
      const raw = getComputedStyle(document.documentElement).getPropertyValue(
        "--wra-cookie-banner-height",
      );
      const n = parseFloat(raw);
      setCookiePx(Number.isFinite(n) ? n : 0);
    };
    read();
    const ro = new ResizeObserver(read);
    ro.observe(document.documentElement);
    window.addEventListener(COOKIE_CONSENT_EVENT, read);
    window.addEventListener("resize", read);
    return () => {
      ro.disconnect();
      window.removeEventListener(COOKIE_CONSENT_EVENT, read);
      window.removeEventListener("resize", read);
    };
  }, []);

  return cookiePx;
}
