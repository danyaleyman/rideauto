"use client";

import Link from "next/link";
import { useEffect } from "react";
import { Button } from "@/components/ui/button";

export default function CatalogError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("catalog segment error", error);
  }, [error]);

  return (
    <div className="mx-auto min-h-[50vh] max-w-lg px-4 py-16 text-center">
      <h1 className="text-lg font-semibold tracking-tight text-foreground">Каталог временно недоступен</h1>
      <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
        Произошла ошибка при отображении страницы. Попробуйте ещё раз или откройте каталог заново.
      </p>
      {error.message ? (
        <p className="mt-2 break-words font-mono text-xs text-muted-foreground">{error.message}</p>
      ) : null}
      <div className="mt-6 flex flex-col items-center justify-center gap-3 sm:flex-row sm:flex-wrap">
        <Button type="button" className="rounded-full" onClick={() => reset()}>
          Повторить
        </Button>
        <Button type="button" variant="outline" className="rounded-full" asChild>
          <Link href="/catalog">Открыть каталог</Link>
        </Button>
        <Button type="button" variant="outline" className="rounded-full" asChild>
          <Link href="/contacts">Контакты</Link>
        </Button>
      </div>
    </div>
  );
}
