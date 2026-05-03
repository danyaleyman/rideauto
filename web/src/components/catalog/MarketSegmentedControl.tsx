"use client";

import { cn } from "@/lib/utils";
import type { Market } from "@/lib/catalog-url";

export function MarketSegmentedControl({
  market,
  onChange,
}: {
  market: Market;
  onChange: (m: Market) => void;
}) {
  return (
    <div
      className="relative grid h-11 w-full min-w-0 grid-cols-2 rounded-full bg-muted/70 p-1 ring-1 ring-border/50 dark:bg-muted/40"
      role="tablist"
      aria-label="Рынок: Корея или Китай"
      onKeyDown={(e) => {
        if (e.key === "ArrowRight" || e.key === "ArrowLeft") {
          e.preventDefault();
          onChange(market === "korea" ? "china" : "korea");
        }
      }}
    >
      <div
        className={cn(
          "pointer-events-none absolute top-1 bottom-1 w-[calc(50%-4px)] rounded-full bg-background shadow-md ring-1 ring-border/60 transition-[inset-inline-start] duration-200 ease-out dark:bg-card dark:ring-border/40",
          market === "korea" ? "start-1" : "start-[calc(50%+2px)]",
        )}
        aria-hidden
      />
      <button
        type="button"
        role="tab"
        aria-selected={market === "korea"}
        tabIndex={market === "korea" ? 0 : -1}
        className={cn(
          "relative z-10 min-w-0 rounded-full px-1 py-2 text-sm font-medium leading-snug transition-colors [overflow-wrap:anywhere]",
          market === "korea" ? "text-foreground" : "text-muted-foreground",
        )}
        onClick={() => onChange("korea")}
      >
        Корея
      </button>
      <button
        type="button"
        role="tab"
        aria-selected={market === "china"}
        tabIndex={market === "china" ? 0 : -1}
        className={cn(
          "relative z-10 min-w-0 rounded-full px-1 py-2 text-sm font-medium leading-snug transition-colors [overflow-wrap:anywhere]",
          market === "china" ? "text-foreground" : "text-muted-foreground",
        )}
        onClick={() => onChange("china")}
      >
        Китай
      </button>
    </div>
  );
}
