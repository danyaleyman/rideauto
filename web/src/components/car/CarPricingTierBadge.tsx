"use client";

import { CircleHelp } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

/** Чип слоя цены на странице авто (как в списке каталога). */
export function CarPricingTierBadge({
  tier,
  className,
}: {
  tier: string | null | undefined;
  className?: string;
}) {
  const t = (tier || "").trim();
  if (t === "korea_land_only") {
    return (
      <Badge
        variant="outline"
        className={cn(
          "inline-flex h-auto max-w-full items-center gap-1 rounded-full border-amber-500/35 bg-amber-500/10 px-3 py-1 text-xs font-medium text-amber-950 dark:text-amber-100",
          className,
        )}
      >
        Без таможни РФ
        <Tooltip>
          <TooltipTrigger asChild>
            <button type="button" className="inline-flex shrink-0" aria-label="Пояснение: цена без растаможки РФ">
              <CircleHelp className="size-3.5 opacity-80" />
            </button>
          </TooltipTrigger>
          <TooltipContent side="top" className="max-w-[20rem]">
            Указанная сумма — Корея, логистика и сопутствующие сборы по данным каталога; растаможка в РФ в эту цифру не
            входит и считается отдельно.
          </TooltipContent>
        </Tooltip>
      </Badge>
    );
  }
  if (t === "price_on_request") {
    return (
      <Badge variant="secondary" className={cn("rounded-full px-3 py-1 text-xs font-medium", className)}>
        Цена по запросу
      </Badge>
    );
  }
  if (t === "full_customs") {
    return (
      <Badge variant="outline" className={cn("rounded-full border-primary/25 bg-primary/5 px-3 py-1 text-xs font-medium", className)}>
        Оценка под ключ (с таможней РФ)
      </Badge>
    );
  }
  return null;
}
