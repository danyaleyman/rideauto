"use client";

import Link from "next/link";
import { motion, useReducedMotion } from "framer-motion";
import type { CarListingAvailability } from "@/lib/car-listing-trust";
import { MOTION_PRESETS, MOTION_TOKENS } from "@/components/ui/motion";
import { cn } from "@/lib/utils";

type Props = {
  priceLine: string;
  availability?: CarListingAvailability;
};

/** Фиксированная панель цены + CTA на телефоне (как у агрегаторов). */
export function CarStickyMobileBar({ priceLine, availability = "available" }: Props) {
  const reduceMotion = useReducedMotion();

  const caption =
    availability === "sold" || availability === "reserved"
      ? "Статус объявления"
      : "Стоимость в России под ключ";

  return (
    <motion.div
      className={cn(
        "fixed inset-x-0 bottom-0 z-40 lg:hidden",
        "border-t border-border/60 bg-background/95",
        "shadow-[0_-12px_40px_-8px_rgba(0,0,0,0.12)]",
        "backdrop-blur-xl dark:shadow-[0_-12px_40px_-8px_rgba(0,0,0,0.45)]",
      )}
      style={{ paddingBottom: "max(0.65rem, env(safe-area-inset-bottom))" }}
      initial={reduceMotion ? false : { opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={reduceMotion ? { duration: 0.01 } : { duration: 0.24, ease: MOTION_TOKENS.easeSoft }}
    >
      <div className="mx-auto flex max-w-lg flex-col gap-2.5 px-4 pt-3 min-[420px]:flex-row min-[420px]:items-end min-[420px]:justify-between min-[420px]:gap-3">
        <div className="min-w-0 w-full flex-1 pb-0 min-[420px]:pb-0.5">
          <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">{caption}</p>
          <p
            className={cn(
              "text-lg font-bold leading-tight tracking-tight [overflow-wrap:anywhere] tabular-nums",
              availability === "sold"
                ? "text-red-700 dark:text-red-300"
                : availability === "reserved"
                  ? "text-amber-800 dark:text-amber-200"
                  : "text-foreground",
            )}
          >
            {priceLine}
          </p>
        </div>
        <motion.div {...(reduceMotion ? {} : MOTION_PRESETS.pressable)}>
          <Link
            href="/contacts"
            className="flex w-full min-h-11 shrink-0 items-center justify-center rounded-xl bg-blue-600 px-4 py-3 text-center text-sm font-semibold text-white shadow-md transition-colors hover:bg-blue-700 active:scale-[0.98] min-[420px]:w-auto min-[420px]:px-5"
          >
            Менеджер
          </Link>
        </motion.div>
      </div>
    </motion.div>
  );
}
