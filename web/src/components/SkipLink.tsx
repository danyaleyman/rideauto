"use client";

import { useLocaleContext } from "@/components/LocaleProvider";

/** Ссылка «Перейти к содержимому» — WCAG 2.4.1 (Bypass Blocks). */
export function SkipLink() {
  const { t } = useLocaleContext();
  return (
    <a
      href="#main"
      className="sr-only focus:not-sr-only focus:fixed focus:start-4 focus:top-4 focus:z-[100] focus:rounded-md focus:bg-background focus:px-4 focus:py-2 focus:text-sm focus:font-medium focus:text-foreground focus:shadow-lg focus:ring-2 focus:ring-ring"
    >
      {t("common.skipToContent")}
    </a>
  );
}
