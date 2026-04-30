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
    <div className="fixed inset-x-0 bottom-0 z-50 border-t border-border/70 bg-background/95 p-3 shadow-2xl backdrop-blur sm:p-4">
      <div className="mx-auto flex max-w-[1100px] flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <p className="text-sm text-muted-foreground">
          Мы используем обязательные cookie для работы сайта и можем использовать аналитические cookie только с вашего
          согласия. Подробнее в{" "}
          <Link href="/cookies" className="underline underline-offset-4 hover:text-foreground">
            Политике cookie
          </Link>{" "}
          и{" "}
          <Link href="/privacy" className="underline underline-offset-4 hover:text-foreground">
            Политике конфиденциальности
          </Link>
          .
        </p>
        <div className="flex shrink-0 gap-2">
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
