"use client";

import { CircleHelp } from "lucide-react";
import { useLocaleContext } from "@/components/LocaleProvider";
import { ListingChip } from "@/components/ui/listing-chip";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

/** Чип слоя цены на странице авто (как в списке каталога). */
export function CarPricingTierBadge({
  tier,
  className,
  size = "md",
}: {
  tier: string | null | undefined;
  className?: string;
  size?: "sm" | "md";
}) {
  const { t } = useLocaleContext();
  const tierKey = (tier || "").trim();
  if (tierKey === "korea_land_only") {
    return (
      <ListingChip size={size} tone="commerceAmber" className={className}>
        {t("car.tier.landOnly")}
        <Tooltip>
          <TooltipTrigger asChild>
            <button type="button" className="inline-flex shrink-0" aria-label={t("catalog.card.noCustomsAria")}>
              <CircleHelp className="size-3.5 opacity-80" />
            </button>
          </TooltipTrigger>
          <TooltipContent side="top" className="max-w-[20rem]">
            {t("catalog.card.noCustomsTip")}
          </TooltipContent>
        </Tooltip>
      </ListingChip>
    );
  }
  if (tierKey === "price_on_request") {
    return (
      <ListingChip size={size} tone="neutral" className={cn("bg-muted/80", className)}>
        {t("car.tier.priceOnRequest")}
      </ListingChip>
    );
  }
  if (tierKey === "full_customs") {
    return (
      <ListingChip size={size} tone="brand" className={className}>
        {t("car.tier.fullCustoms")}
      </ListingChip>
    );
  }
  return null;
}
