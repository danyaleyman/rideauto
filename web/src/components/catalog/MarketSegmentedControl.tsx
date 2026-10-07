"use client";

import { useMemo } from "react";
import { Globe2 } from "lucide-react";
import { CatalogFilterFlatSection } from "@/components/catalog/CatalogFilterSection";
import { useLocaleContext } from "@/components/LocaleProvider";
import { Button } from "@/components/ui/button";
import type { Market } from "@/lib/catalog-url";
import { cn } from "@/lib/utils";

const MARKET_ORDER: readonly Market[] = ["china", "korea", "usa"];

export function MarketSegmentedControl({
  market,
  onChange,
}: {
  market: Market;
  onChange: (m: Market) => void;
}) {
  const { t } = useLocaleContext();
  const items = useMemo(
    () =>
      MARKET_ORDER.map((value) => ({
        value,
        label: t(`catalog.market.${value}`),
      })),
    [t],
  );
  const summary = t(`catalog.market.${market}`);

  return (
    <CatalogFilterFlatSection
      icon={Globe2}
      title={t("catalog.market.sectionTitle")}
      hint={t("catalog.market.sectionHint")}
      summary={summary}
    >
      <div
        role="radiogroup"
        aria-label={t("catalog.market.ariaLabel")}
        className="grid grid-cols-3 gap-2"
      >
        {items.map((item) => {
          const selected = market === item.value;
          return (
            <Button
              key={item.value}
              type="button"
              role="radio"
              aria-checked={selected}
              variant={selected ? "default" : "outline"}
              className={cn(
                "h-11 w-full rounded-xl px-2 text-sm font-semibold",
                selected && "shadow-sm",
              )}
              onClick={() => {
                if (!selected) onChange(item.value);
              }}
            >
              {item.label}
            </Button>
          );
        })}
      </div>
    </CatalogFilterFlatSection>
  );
}
