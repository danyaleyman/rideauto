"use client";

import { useLocaleContext } from "@/components/LocaleProvider";

export default function CarLoading() {
  const { t } = useLocaleContext();
  return (
    <div className="mx-auto max-w-6xl px-4 py-8">
      <div className="mb-6 rounded border border-zinc-200 bg-zinc-50 px-3 py-2 text-sm text-zinc-500 dark:border-border dark:bg-muted/30 dark:text-muted-foreground">
        {t("catalog.card.loading")}
      </div>
    </div>
  );
}
