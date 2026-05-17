"use client";

import type { LucideIcon } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { MotionStagger, MotionStaggerItem } from "@/components/ui/motion";
import { catalogCardAttributeChips } from "@/lib/catalog-client-utils";
import { cn } from "@/lib/utils";

type Variant = "catalog" | "detail";

const variantClasses: Record<Variant, string> = {
  catalog:
    "inline-flex h-auto max-w-full items-center gap-1 rounded-full border-border/55 bg-background/55 px-2.5 py-1 text-[11px] font-medium normal-case text-foreground shadow-none [overflow-wrap:anywhere] max-sm:border-dashed max-sm:text-muted-foreground dark:bg-muted/20",
  detail:
    "inline-flex h-auto w-full max-w-full items-start gap-1.5 rounded-2xl border-border/70 py-2 ps-2.5 pe-3 text-left text-xs font-medium normal-case shadow-sm sm:inline-flex sm:w-auto sm:max-w-none sm:rounded-full sm:items-center",
};

/** Единые чипы характеристик: каталог и страница авто. */
export function CarListingAttributeChips({
  data,
  yearNum,
  variant = "catalog",
  className,
  animated = false,
}: {
  data: Record<string, unknown>;
  yearNum?: number | null;
  variant?: Variant;
  className?: string;
  animated?: boolean;
}) {
  const chips = catalogCardAttributeChips(data, yearNum);
  if (!chips.length) return null;

  const badgeVariant = variant === "detail" ? "outline" : "outline";
  const list = (
    <ul
      className={cn(
        "flex min-w-0 flex-wrap gap-1.5 md:gap-2",
        variant === "detail" && "gap-2",
        className,
      )}
      aria-label="Краткие характеристики"
    >
      {chips.map((c) => {
        const Icon = c.Icon as LucideIcon;
        return (
          <li key={c.key} className="min-w-0 max-w-full">
            <Badge variant={badgeVariant} className={variantClasses[variant]}>
              <Icon
                className={cn(
                  "size-3 shrink-0 opacity-80",
                  variant === "detail" && "mt-0.5 size-3.5 sm:mt-0",
                )}
                aria-hidden
              />
              <span className={cn("min-w-0", variant === "detail" && "flex-1 [overflow-wrap:anywhere]")}>
                {c.label}
              </span>
            </Badge>
          </li>
        );
      })}
    </ul>
  );

  if (animated && variant === "detail") {
    return (
      <MotionStagger className="mt-4 flex min-w-0 flex-wrap gap-2" aria-label="Краткие характеристики">
        {chips.map((c) => {
          const Icon = c.Icon as LucideIcon;
          return (
            <MotionStaggerItem key={c.key} className="min-w-0 max-w-full">
              <Badge variant="outline" className={variantClasses.detail}>
                <Icon className="mt-0.5 size-3.5 shrink-0 opacity-80 sm:mt-0" aria-hidden />
                <span className="min-w-0 flex-1 [overflow-wrap:anywhere]">{c.label}</span>
              </Badge>
            </MotionStaggerItem>
          );
        })}
      </MotionStagger>
    );
  }

  return list;
}
