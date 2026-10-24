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
        data-testid="catalog-market"
        className="grid grid-cols-3 gap-1 rounded-lg bg-muted p-1"
      >
        {items.map((item) => {
          const selected = market === item.value;
          return (
            <Button
              key={item.value}
              type="button"
              role="radio"
              aria-checked={selected}
              variant="ghost"
              data-testid={`catalog-market-${item.value}`}
              className={cn(
                "h-9 w-full rounded-md px-2 text-sm font-medium",
                selected
                  ? "bg-background text-foreground shadow-sm hover:bg-background"
                  : "text-foreground/70 hover:bg-transparent hover:text-foreground",
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
