"use client";

import Link from "next/link";
import { useEffect } from "react";
import { Button } from "@/components/ui/button";

export default function CarError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("car segment error", error);
  }, [error]);

  return (
    <div className="mx-auto min-h-[40vh] max-w-lg px-4 py-16 text-center">
      <h1 className="text-lg font-semibold tracking-tight text-foreground">Не удалось показать автомобиль</h1>
      <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
        Обновите страницу или вернитесь в каталог.
      </p>
      <div className="mt-6 flex flex-col items-center justify-center gap-3 sm:flex-row sm:flex-wrap">
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
