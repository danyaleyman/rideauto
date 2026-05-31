"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { useLocaleContext } from "@/components/LocaleProvider";
import { Button } from "@/components/ui/button";
import {
  COOKIE_CONSENT_OPEN_EVENT,
  readCookieConsent,
  writeCookieConsent,
} from "@/lib/cookie-consent";

function setCookieBannerHeight(px: number) {
  document.documentElement.style.setProperty("--wra-cookie-banner-height", `${px}px`);
}

export function CookieConsentBanner() {
  const { t } = useLocaleContext();
  const [open, setOpen] = useState(false);
  const barRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setOpen(!readCookieConsent());
    const onOpen = () => setOpen(true);
    window.addEventListener(COOKIE_CONSENT_OPEN_EVENT, onOpen);
    return () => window.removeEventListener(COOKIE_CONSENT_OPEN_EVENT, onOpen);
  }, []);

  useEffect(() => {
    const el = barRef.current;
    if (!open || !el) {
      setCookieBannerHeight(0);
      return;
    }
    const sync = () => setCookieBannerHeight(el.offsetHeight);
    sync();
    const ro = new ResizeObserver(sync);
    ro.observe(el);
    window.addEventListener("resize", sync);
    return () => {
      ro.disconnect();
      window.removeEventListener("resize", sync);
      setCookieBannerHeight(0);
    };
  }, [open]);

  if (!open) return null;

  return (
    <div
      ref={barRef}
      role="dialog"
      aria-label={t("cookie.ariaLabel")}
      className="fixed inset-x-0 bottom-0 z-50 border-t-2 border-primary/25 bg-background/95 p-3 pb-[max(0.75rem,env(safe-area-inset-bottom))] shadow-[0_-8px_30px_rgba(0,0,0,0.12)] backdrop-blur-md sm:p-4"
    >
      <div className="mx-auto flex max-w-[1100px] flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <p className="text-sm text-foreground/90 [overflow-wrap:anywhere]">
          {t("cookie.body")}{" "}
          <Link
            href="/cookies"
            className="font-medium text-brand underline underline-offset-4 hover:text-brand/90"
          >
            {t("cookie.policyCookies")}
          </Link>{" "}
          {t("cookie.and")}{" "}
          <Link
            href="/privacy"
            className="font-medium text-brand underline underline-offset-4 hover:text-brand/90"
          >
            {t("cookie.policyPrivacy")}
          </Link>
          .
        </p>
        <div className="flex shrink-0 flex-wrap gap-2">
          <Button
            type="button"
            variant="outline"
            className="min-h-10 rounded-2xl px-3 text-xs sm:text-sm"
            onClick={() => {
              writeCookieConsent({ analytics: false, marketing: false });
              setOpen(false);
            }}
          >
            {t("cookie.essentialOnly")}
          </Button>
          <Button
            type="button"
            className="min-h-10 rounded-2xl px-3 text-xs sm:text-sm"
            onClick={() => {
              writeCookieConsent({ analytics: true, marketing: false });
              setOpen(false);
            }}
          >
            {t("cookie.accept")}
          </Button>
        </div>
      </div>
    </div>
  );
}
