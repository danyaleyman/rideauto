"use client";

import type { ReactNode } from "react";
import { CircleHelp } from "lucide-react";
import { useLocaleContext } from "@/components/LocaleProvider";
import { ListingChip } from "@/components/ui/listing-chip";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { carPassabilityStatus } from "@/lib/catalog-client-utils";
import { extractPricingTier } from "@/lib/pricing-tier-ui";
import { CarPricingTierBadge } from "@/components/car/CarPricingTierBadge";
import { cn } from "@/lib/utils";

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
  const { t } = useLocaleContext();
  const tier = extractPricingTier(data);
  const passability = carPassabilityStatus(data, yearNum);
  const chipSize = size === "compact" ? "sm" : "md";

  if (!tier && !passability) return null;

  return (
    <div className={cn("flex min-w-0 flex-wrap items-center gap-2", className)}>
      {tier ? <CarPricingTierBadge tier={tier} size={chipSize} /> : null}
      {passability === "passable" ? (
        <ListingChip size={chipSize} tone="commerceEmerald">
          {t("catalog.card.passable")}
          <PassabilityHelp ariaLabel={t("catalog.card.passableAria")}>{t("catalog.card.passableTip")}</PassabilityHelp>
        </ListingChip>
      ) : null}
      {passability === "young" || passability === "old" ? (
        <ListingChip size={chipSize} tone="commerceAmber">
          {t("catalog.card.highRate")}
          <PassabilityHelp
            ariaLabel={passability === "young" ? t("catalog.card.youngAria") : t("catalog.card.oldAria")}
          >
            {passability === "young" ? t("catalog.card.youngTip") : t("catalog.card.oldTip")}
          </PassabilityHelp>
        </ListingChip>
      ) : null}
    </div>
  );
}
