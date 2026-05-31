"use client";

import type { LucideIcon } from "lucide-react";
import { ListingChip } from "@/components/ui/listing-chip";
import { MotionStagger, MotionStaggerItem } from "@/components/ui/motion";
import { useLocaleContext } from "@/components/LocaleProvider";
import { catalogCardAttributeChips } from "@/lib/catalog-client-utils";
import { cn } from "@/lib/utils";

/** Единые чипы характеристик: каталог и страница авто. */
export function CarListingAttributeChips({
  data,
  yearNum,
  className,
  animated = false,
  size = "md",
}: {
  data: Record<string, unknown>;
  yearNum?: number | null;
  className?: string;
  animated?: boolean;
  size?: "sm" | "md";
}) {
  const { t, locale } = useLocaleContext();
  const chips = catalogCardAttributeChips(data, yearNum, locale);
  if (!chips.length) return null;

  const chipEl = (c: { key: string; label: string; Icon: LucideIcon }) => {
    const Icon = c.Icon;
    return (
      <ListingChip key={c.key} size={size} tone="neutral" className="normal-case">
        <Icon className="size-3 shrink-0 opacity-80 sm:size-3.5" aria-hidden />
        <span className="min-w-0">{c.label}</span>
      </ListingChip>
    );
  };

  const list = (
    <ul
      className={cn("flex min-w-0 flex-wrap gap-1.5 md:gap-2", className)}
      aria-label={t("catalog.card.attrList")}
    >
      {chips.map((c) => (
        <li key={c.key} className="min-w-0 max-w-full">
          {chipEl(c)}
        </li>
      ))}
    </ul>
  );

  if (animated) {
    return (
      <MotionStagger className={cn("mt-4 flex min-w-0 flex-wrap gap-2", className)} aria-label={t("catalog.card.attrList")}>
        {chips.map((c) => (
          <MotionStaggerItem key={c.key} className="min-w-0 max-w-full">
            {chipEl(c)}
          </MotionStaggerItem>
        ))}
      </MotionStagger>
    );
  }

  return list;
}
