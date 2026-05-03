"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import {
  COOKIE_CONSENT_OPEN_EVENT,
  readCookieConsent,
  writeCookieConsent,
} from "@/lib/cookie-consent";

export function CookieConsentBanner() {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    setOpen(!readCookieConsent());
    const onOpen = () => setOpen(true);
    window.addEventListener(COOKIE_CONSENT_OPEN_EVENT, onOpen);
    return () => window.removeEventListener(COOKIE_CONSENT_OPEN_EVENT, onOpen);
  }, []);

  if (!open) return null;

  return (
    <div
      role="dialog"
      aria-label="Согласие на использование cookie"
      className="fixed inset-x-0 bottom-0 z-50 border-t-2 border-primary/25 bg-background/95 p-3 pb-[max(0.75rem,env(safe-area-inset-bottom))] shadow-[0_-8px_30px_rgba(0,0,0,0.12)] backdrop-blur-md sm:p-4 sm:pb-4"
    >
      <div className="mx-auto flex max-w-[1100px] flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <p className="text-sm text-foreground/90 [overflow-wrap:anywhere]">
          Мы используем обязательные cookie для работы сайта и можем использовать аналитические cookie только с вашего
          согласия. Подробнее в{" "}
          <Link
            href="/cookies"
            className="font-medium text-primary underline underline-offset-4 hover:text-primary/90"
          >
            Политике cookie
          </Link>{" "}
          и{" "}
          <Link
            href="/privacy"
            className="font-medium text-primary underline underline-offset-4 hover:text-primary/90"
          >
            Политике конфиденциальности
          </Link>
          .
        </p>
        <div className="flex shrink-0 flex-wrap gap-2">
          <Button
            type="button"
            variant="outline"
            className="h-9 rounded-lg px-3 text-xs sm:text-sm"
            onClick={() => {
              writeCookieConsent({ analytics: false, marketing: false });
              setOpen(false);
            }}
          >
            Только необходимые
          </Button>
          <Button
            type="button"
            className="h-9 rounded-lg px-3 text-xs sm:text-sm"
            onClick={() => {
              writeCookieConsent({ analytics: true, marketing: false });
              setOpen(false);
            }}
          >
            Принять
          </Button>
        </div>
      </div>
    </div>
  );
}
