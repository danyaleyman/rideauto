"use client";

import { Button } from "@/components/ui/button";
import { catalogSearchErrorHint } from "@/lib/catalog-client-utils";
import { showCatalogEngineeringNotices } from "@/lib/catalog-dev-ui";
import { useLocaleContext } from "@/components/LocaleProvider";

export function CatalogStatusBanners({
  online,
  showSsrDegradedNotice,
  err,
  onRetry,
}: {
  online: boolean;
  showSsrDegradedNotice: boolean;
  err: string | null;
  onRetry: () => void;
}) {
  const { locale, t } = useLocaleContext();
  const showEngineering = showCatalogEngineeringNotices();

  return (
    <>
      {!online ? (
        <div
          className="mb-4 rounded-xl border border-amber-600/35 bg-amber-500/10 px-4 py-3 text-sm text-amber-950 [overflow-wrap:anywhere] dark:text-amber-50"
          role="alert"
        >
          <p className="font-medium">{t("catalog.offline.title")}</p>
          <p className="mt-1 text-amber-900/90 dark:text-amber-100/90">{t("catalog.offline.hint")}</p>
        </div>
      ) : null}

      {showSsrDegradedNotice && showEngineering ? (
        <div
          className="mb-4 rounded-xl border border-amber-500/35 bg-amber-500/10 px-4 py-3 text-sm text-amber-950 [overflow-wrap:anywhere] dark:text-amber-50"
          role="status"
        >
          Не удалось получить каталог при отрисовке на сервере — загружаем выдачу в браузере. Проверьте логи API и
          переменную <code className="break-all rounded bg-background/80 px-1 dark:bg-background/40">WRA_API_INTERNAL</code> в
          контейнере <code className="rounded bg-background/80 px-1 dark:bg-background/40">web</code>. Для клиента по
          умолчанию используются запросы на тот же сайт (<code className="rounded bg-background/80 px-1">/api/…</code>); не
          задавайте <code className="rounded bg-background/80 px-1">NEXT_PUBLIC_API_BASE=http://127.0.0.1:8080</code>, если
          открываете сайт не с localhost.
        </div>
      ) : showSsrDegradedNotice ? (
        <div
          className="mb-4 rounded-xl border border-amber-500/35 bg-amber-500/10 px-4 py-3 text-sm text-amber-950 dark:text-amber-50"
          role="status"
        >
          {t("catalog.error.ssrLoading")}
        </div>
      ) : null}

      {err ? (
        <div className="mb-4 rounded-xl border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm [overflow-wrap:anywhere]">
          <p className="font-medium text-destructive">{t("catalog.error.title")}</p>
          <p className="mt-1 text-destructive/90">{err}</p>
          {catalogSearchErrorHint(err, locale) ? (
            <p className="mt-2 text-muted-foreground">{catalogSearchErrorHint(err, locale)}</p>
          ) : null}
          {showEngineering ? (
            <p className="mt-2 text-xs text-muted-foreground">
              Убедитесь, что API отвечает (логи сервиса <code className="rounded bg-background/80 px-1">api</code>). В Docker не
              используйте для браузера <code className="rounded bg-background/80 px-1">127.0.0.1:8080</code>, если заходите по IP
              или домену — оставьте <code className="rounded bg-background/80 px-1">NEXT_PUBLIC_API_BASE</code> пустым или
              укажите публичный URL с тем же host, что и сайт.
            </p>
          ) : null}
          <Button type="button" variant="secondary" size="sm" className="mt-3 rounded-full" onClick={onRetry}>
            {t("catalog.error.retry")}
          </Button>
        </div>
      ) : null}
    </>
  );
}
