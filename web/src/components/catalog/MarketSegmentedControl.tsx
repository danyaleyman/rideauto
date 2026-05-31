"use client";

import { useMemo } from "react";
import { useLocaleContext } from "@/components/LocaleProvider";
import { SegmentedControlPill } from "@/components/ui/segmented-control";
import type { Market } from "@/lib/catalog-url";

export function MarketSegmentedControl({
  market,
  onChange,
}: {
  market: Market;
  onChange: (m: Market) => void;
}) {
  const { t } = useLocaleContext();
  const items = useMemo(
    () => [
      { value: "korea" as const, label: t("catalog.market.korea") },
      { value: "china" as const, label: t("catalog.market.china") },
    ],
    [t],
  );

  return (
    <SegmentedControlPill
      value={market}
      onChange={onChange}
      items={items}
      aria-label={t("catalog.market.ariaLabel")}
    />
  );
}
