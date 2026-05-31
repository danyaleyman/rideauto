"use client";

import { Button } from "@/components/ui/button";
import { useLocaleContext } from "@/components/LocaleProvider";
import type { AppLocale } from "@/lib/i18n";
import { cn } from "@/lib/utils";

export function LocaleSwitcher({ className }: { className?: string }) {
  const { locale, setLocale, t } = useLocaleContext();

  const btn = (code: AppLocale, labelKey: string) => (
    <Button
      type="button"
      variant={locale === code ? "default" : "ghost"}
      size="sm"
      className="h-7 min-w-8 rounded-full px-2 text-xs"
      aria-pressed={locale === code}
      onClick={() => {
        if (locale !== code) setLocale(code);
      }}
    >
      {t(labelKey)}
    </Button>
  );

  return (
    <div className={cn("inline-flex items-center gap-0.5 rounded-full border border-border/70 p-0.5", className)}>
      {btn("ru", "header.localeRu")}
      {btn("en", "header.localeEn")}
    </div>
  );
}
