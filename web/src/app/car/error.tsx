"use client";

import Link from "next/link";
import { useEffect } from "react";
import { useLocaleContext } from "@/components/LocaleProvider";
import { Button } from "@/components/ui/button";
import { reportClientError } from "@/lib/observability";

export default function CarError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  const { t } = useLocaleContext();
  useEffect(() => {
    reportClientError(error, { area: "car_error_boundary" });
  }, [error]);

  return (
    <div className="mx-auto min-h-[40vh] max-w-lg px-4 py-16 text-center">
      <h1 className="text-lg font-semibold tracking-tight text-foreground">{t("car.error.title")}</h1>
      <p className="mt-3 text-sm leading-relaxed text-muted-foreground">{t("car.error.hint")}</p>
      <div className="mt-6 flex flex-col items-center justify-center gap-3 sm:flex-row sm:flex-wrap">
        <Button type="button" className="rounded-full" onClick={() => reset()}>
          {t("common.retry")}
        </Button>
        <Button type="button" variant="outline" className="rounded-full" asChild>
          <Link href="/catalog">{t("car.error.openCatalog")}</Link>
        </Button>
        <Button type="button" variant="outline" className="rounded-full" asChild>
          <Link href="/contacts">{t("common.contacts")}</Link>
        </Button>
      </div>
    </div>
  );
}
