"use client";

import dynamic from "next/dynamic";
import { useLocaleContext } from "@/components/LocaleProvider";

function CalcLoading() {
  const { t } = useLocaleContext();
  return (
    <div
      className="mt-6 min-h-[16rem] animate-pulse rounded-2xl border border-border/50 bg-muted/30"
      role="status"
      aria-busy="true"
      aria-live="polite"
    >
      <span className="sr-only">{t("buy.calcLoading")}</span>
    </div>
  );
}

export const BuyCalculatorLazy = dynamic(() => import("./BuyCalculator"), {
  ssr: false,
  loading: () => <CalcLoading />,
});
