"use client";

import { useEffect, useMemo, useState } from "react";
import { createT, type AppLocale } from "@/lib/i18n";
import { LOCALE_COOKIE } from "@/lib/locale-constants";
import { reportClientError } from "@/lib/observability";

function readLocaleCookie(): AppLocale {
  try {
    const m = document.cookie.match(new RegExp(`(?:^|; )${LOCALE_COOKIE}=([^;]*)`));
    const v = m ? decodeURIComponent(m[1]) : "";
    return v === "en" || v === "ru" ? v : "ru";
  } catch {
    return "ru";
  }
}

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  const [locale, setLocale] = useState<AppLocale>("ru");
  const t = useMemo(() => createT(locale), [locale]);

  useEffect(() => {
    reportClientError(error, { area: "global_error_boundary" });
    const fromCookie = readLocaleCookie();
    setLocale(fromCookie);
    document.documentElement.lang = fromCookie;
  }, [error]);

  return (
    <html lang={locale}>
      <body className="min-h-screen bg-background font-sans text-foreground antialiased">
        <div className="mx-auto flex min-h-screen max-w-lg flex-col justify-center px-4 py-16 text-center">
          <h1 className="text-lg font-semibold">{t("site.globalErrorTitle")}</h1>
          <p className="mt-3 text-sm text-muted-foreground">{t("site.globalErrorHint")}</p>
          <button
            type="button"
            className="mt-6 rounded-full bg-primary px-5 py-2 text-sm font-medium text-primary-foreground"
            onClick={() => reset()}
          >
            {t("common.retry")}
          </button>
        </div>
      </body>
    </html>
  );
}
