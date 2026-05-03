"use client";

import dynamic from "next/dynamic";

/** Тяжёлый калькулятор подгружается отдельным чанком после первого рендера страницы «Как купить». */
export const BuyCalculatorLazy = dynamic(() => import("./BuyCalculator"), {
  ssr: false,
  loading: () => (
    <div
      className="mt-6 min-h-[16rem] animate-pulse rounded-2xl border border-border/50 bg-muted/30"
      role="status"
      aria-busy="true"
      aria-live="polite"
    >
      <span className="sr-only">Загрузка калькулятора…</span>
    </div>
  ),
});
