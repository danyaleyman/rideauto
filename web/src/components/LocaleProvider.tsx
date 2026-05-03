"use client";

import { createContext, useCallback, useContext, useMemo, useState } from "react";
import type { AppLocale } from "@/lib/i18n";
import { createT } from "@/lib/i18n";
import { LOCALE_COOKIE } from "@/lib/locale-constants";

type Ctx = {
  locale: AppLocale;
  /** Обновляет cookie и перезагружает страницу. */
  setLocale: (next: AppLocale) => void;
  t: (path: string) => string;
};

const LocaleContext = createContext<Ctx | null>(null);

export function LocaleProvider({
  initialLocale,
  children,
}: {
  initialLocale: AppLocale;
  children: React.ReactNode;
}) {
  const [locale, setLocaleState] = useState<AppLocale>(initialLocale);
  const t = useMemo(() => createT(locale), [locale]);

  const setLocale = useCallback((next: AppLocale) => {
    setLocaleState(next);
    try {
      document.cookie = `${LOCALE_COOKIE}=${next}; path=/; max-age=${60 * 60 * 24 * 365}; samesite=lax`;
    } catch {
      // ignore
    }
    window.location.reload();
  }, []);

  const value = useMemo(() => ({ locale, setLocale, t }), [locale, setLocale, t]);

  return <LocaleContext.Provider value={value}>{children}</LocaleContext.Provider>;
}

export function useLocaleContext(): Ctx {
  const v = useContext(LocaleContext);
  if (!v) {
    const t = createT("ru");
    return { locale: "ru", setLocale: () => {}, t };
  }
  return v;
}
