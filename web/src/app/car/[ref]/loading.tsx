"use client";

import { useLocaleContext } from "@/components/LocaleProvider";

export default function CarLoading() {
  const { t } = useLocaleContext();
  return (
    <div className="mx-auto max-w-6xl px-4 py-8" role="status" aria-busy="true">
      <span className="sr-only">{t("catalog.card.loading")}</span>

      {/* Хлебные крошки */}
      <div className="mb-6 h-4 w-2/3 max-w-sm animate-pulse rounded bg-muted" />

      {/* Галерея 16:9 */}
      <div className="aspect-video w-full animate-pulse rounded-xl bg-muted" />

      {/* Заголовок */}
      <div className="mt-6 h-8 w-3/4 max-w-xl animate-pulse rounded bg-muted" />
      <div className="mt-3 h-5 w-1/2 max-w-md animate-pulse rounded bg-muted" />

      {/* Чипы характеристик */}
      <div className="mt-5 flex flex-wrap gap-2">
        <div className="h-8 w-24 animate-pulse rounded-full bg-muted" />
        <div className="h-8 w-28 animate-pulse rounded-full bg-muted" />
        <div className="h-8 w-20 animate-pulse rounded-full bg-muted" />
        <div className="h-8 w-32 animate-pulse rounded-full bg-muted" />
      </div>

      {/* Контент + карточка цены */}
      <div className="mt-8 grid gap-8 lg:grid-cols-[minmax(0,1fr)_380px]">
        <div className="space-y-4">
          <div className="h-4 w-full animate-pulse rounded bg-muted" />
          <div className="h-4 w-full animate-pulse rounded bg-muted" />
          <div className="h-4 w-2/3 animate-pulse rounded bg-muted" />
          <div className="mt-6 h-6 w-40 animate-pulse rounded bg-muted" />
          <div className="h-16 w-full animate-pulse rounded-xl bg-muted" />
          <div className="h-16 w-full animate-pulse rounded-xl bg-muted" />
        </div>
        <div>
          <div className="h-72 w-full animate-pulse rounded-xl bg-muted" />
        </div>
      </div>
    </div>
  );
}
