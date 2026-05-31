"use client";

import Link from "next/link";
import { Bookmark, Trash2 } from "lucide-react";
import type { CatalogSearchController } from "@/hooks/use-catalog-search-state";
import { useSavedCatalogSearches } from "@/hooks/use-saved-catalog-searches";
import { useLocaleContext } from "@/components/LocaleProvider";
import { Button } from "@/components/ui/button";

/** Сохранённые фильтры каталога: localStorage без входа, /api/subscriptions после входа. */
export function CatalogSavedSearches({ catalog }: { catalog: CatalogSearchController }) {
  const { t } = useLocaleContext();
  const { items, saveCurrent, remove, hrefFor, notifyByEmail } = useSavedCatalogSearches();

  return (
    <div className="flex min-w-0 flex-col gap-2 border-t border-border/60 pt-3">
      <div className="flex flex-wrap items-center gap-2">
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="h-auto min-h-9 rounded-full gap-1.5 px-3 text-xs"
          onClick={() => void saveCurrent(catalog.state)}
        >
          <Bookmark className="size-3.5 shrink-0" aria-hidden />
          {t("savedSearch.save")}
        </Button>
        {notifyByEmail ? (
          <span className="text-[11px] text-muted-foreground">{t("savedSearch.notifyHint")}</span>
        ) : null}
        {items.length ? (
          <span className="text-xs text-muted-foreground">{t("savedSearch.savedCount", { count: items.length })}</span>
        ) : null}
      </div>
      {items.length ? (
        <ul className="flex min-w-0 flex-col gap-1.5" aria-label={t("savedSearch.listAria")}>
          {items.map((item) => (
            <li key={item.id} className="flex min-w-0 items-center gap-1">
              <Link
                href={hrefFor(item)}
                className="min-w-0 flex-1 truncate rounded-lg px-2 py-1.5 text-xs text-primary underline-offset-2 hover:underline"
              >
                {item.name}
              </Link>
              <Button
                type="button"
                variant="ghost"
                size="icon-sm"
                className="shrink-0 rounded-full"
                aria-label={t("savedSearch.removeNamed", { name: item.name })}
                onClick={() => remove(item.id)}
              >
                <Trash2 className="size-3.5" aria-hidden />
              </Button>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
