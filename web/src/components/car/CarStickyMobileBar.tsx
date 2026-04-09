"use client";

import Link from "next/link";
import { cn } from "@/lib/utils";

type Props = {
  priceLine: string;
};

/** Фиксированная панель цены + CTA на телефоне (как у агрегаторов). */
export function CarStickyMobileBar({ priceLine }: Props) {
  return (
    <div
      className={cn(
        "fixed inset-x-0 bottom-0 z-40 lg:hidden",
        "border-t border-border/60 bg-background/92",
        "shadow-[0_-12px_40px_-8px_rgba(0,0,0,0.12)]",
        "backdrop-blur-xl dark:shadow-[0_-12px_40px_-8px_rgba(0,0,0,0.45)]",
      )}
      style={{ paddingBottom: "max(0.65rem, env(safe-area-inset-bottom))" }}
    >
      <div className="mx-auto flex max-w-lg items-end justify-between gap-3 px-4 pt-3">
        <div className="min-w-0 flex-1 pb-0.5">
          <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
            Оценка в каталоге
          </p>
          <p className="truncate text-lg font-bold tabular-nums tracking-tight text-foreground">{priceLine}</p>
        </div>
        <Link
          href="/contacts"
          className="shrink-0 rounded-xl bg-blue-600 px-5 py-3 text-center text-sm font-semibold text-white shadow-md transition-colors hover:bg-blue-700 active:scale-[0.98]"
        >
          Менеджер
        </Link>
      </div>
    </div>
  );
}
