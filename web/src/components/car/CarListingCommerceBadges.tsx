"use client";

import type { ReactNode } from "react";
import { CircleHelp } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { carPassabilityStatus } from "@/lib/catalog-client-utils";
import { extractPricingTier } from "@/lib/pricing-tier-ui";
import { CarPricingTierBadge } from "@/components/car/CarPricingTierBadge";
import { cn } from "@/lib/utils";

const passabilityBadgeClass =
  "inline-flex h-8 max-w-full items-center gap-1 rounded-full px-2.5 text-[11px] font-medium [overflow-wrap:anywhere]";

function PassabilityHelp({ children, ariaLabel }: { children: ReactNode; ariaLabel: string }) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <button type="button" className="inline-flex shrink-0" aria-label={ariaLabel}>
          <CircleHelp className="size-3.5 opacity-80" />
        </button>
      </TooltipTrigger>
      <TooltipContent side="top" className="max-w-[20rem] text-xs">
        {children}
      </TooltipContent>
    </Tooltip>
  );
}

/** Бейджи цены/таможни/проходности — как в каталоге, для карточки авто. */
export function CarListingCommerceBadges({
  data,
  className,
  size = "default",
  yearNum,
}: {
  data: Record<string, unknown>;
  className?: string;
  size?: "default" | "compact";
  yearNum?: number | null;
}) {
  const tier = extractPricingTier(data);
  const passability = carPassabilityStatus(data, yearNum);
  const compact = size === "compact";

  if (!tier && !passability) return null;

  return (
    <div className={cn("flex min-w-0 flex-wrap items-center gap-2", className)}>
      {tier ? <CarPricingTierBadge tier={tier} className={compact ? "text-[11px]" : undefined} /> : null}
      {passability === "passable" ? (
        <Badge
          variant="outline"
          className={cn(
            passabilityBadgeClass,
            "border-emerald-600/35 bg-emerald-600/[0.08] text-emerald-800 dark:text-emerald-200",
            compact && "h-7 text-[11px]",
          )}
        >
          Проходной
          <PassabilityHelp ariaLabel="Пояснение для проходного автомобиля">
            «Проходной автомобиль»: на него действуют льготные таможенные тарифы.
          </PassabilityHelp>
        </Badge>
      ) : null}
      {passability === "young" || passability === "old" ? (
        <Badge
          variant="outline"
          className={cn(
            passabilityBadgeClass,
            "border-amber-600/35 bg-amber-500/[0.08] text-amber-950 dark:text-amber-100",
            compact && "h-7 text-[11px]",
          )}
        >
          Высокая ставка
          <PassabilityHelp ariaLabel="Пояснение: повышенные таможенные тарифы">
            {passability === "young"
              ? "Автомобиль менее 3 лет: на него действуют повышенные таможенные тарифы."
              : "Автомобиль старше 5 лет: на него действуют повышенные таможенные тарифы."}
          </PassabilityHelp>
        </Badge>
      ) : null}
    </div>
  );
}