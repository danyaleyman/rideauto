"use client";

import Link from "next/link";
import { useEffect } from "react";
import { Button } from "@/components/ui/button";

export default function RootError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("app error boundary", error);
  }, [error]);

  return (
    <div className="mx-auto flex min-h-[60vh] max-w-lg flex-col justify-center px-4 py-16 text-center">
      <h1 className="text-lg font-semibold tracking-tight text-foreground">Что-то пошло не так</h1>
      <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
        Не удалось отобразить страницу. Попробуйте обновить или вернитесь в каталог.
      </p>
      {error.message ? (
        <p className="mt-2 break-words font-mono text-xs text-muted-foreground">{error.message}</p>
      ) : null}
      <div className="mt-6 flex flex-col items-stretch gap-3 sm:flex-row sm:justify-center">
        <Button type="button" className="rounded-full" onClick={() => reset()}>
          Повторить
        </Button>
        <Button type="button" variant="outline" className="rounded-full" asChild>
          <Link href="/catalog">В каталог</Link>
        </Button>
        <Button type="button" variant="outline" className="rounded-full" asChild>
          <Link href="/contacts">Контакты</Link>
        </Button>
      </div>
    </div>
  );
}
