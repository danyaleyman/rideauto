"use client";

import Link from "next/link";
import { useEffect } from "react";
import { useLocaleContext } from "@/components/LocaleProvider";
import { Button } from "@/components/ui/button";
import { reportClientError } from "@/lib/observability";

export default function CatalogError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  const { t } = useLocaleContext();
  useEffect(() => {
    reportClientError(error, { area: "catalog_error_boundary" });
  }, [error]);

  return (
    <div className="mx-auto min-h-[50vh] max-w-lg px-4 py-16 text-center">
      <h1 className="text-lg font-semibold tracking-tight text-foreground">{t("catalog.error.boundaryTitle")}</h1>
      <p className="mt-3 text-sm leading-relaxed text-muted-foreground">{t("catalog.error.boundaryHint")}</p>
      {error.message ? (
        <p className="mt-2 break-words font-mono text-xs text-muted-foreground">{error.message}</p>
      ) : null}
      <div className="mt-6 flex flex-col items-center justify-center gap-3 sm:flex-row sm:flex-wrap">
        <Button type="button" className="rounded-full" onClick={() => reset()}>
          {t("common.retry")}
        </Button>
        <Button type="button" variant="outline" className="rounded-full" asChild>
          <Link href="/catalog">{t("catalog.error.openCatalog")}</Link>
        </Button>
        <Button type="button" variant="outline" className="rounded-full" asChild>
          <Link href="/contacts">{t("common.contacts")}</Link>
        </Button>
      </div>
    </div>
  );
}
