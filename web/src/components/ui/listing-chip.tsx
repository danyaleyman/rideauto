import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "@/lib/utils";
import { pillRadiusClass } from "@/lib/design-system";

const listingChipVariants = cva(
  "inline-flex max-w-full items-center gap-1 font-medium shadow-none [overflow-wrap:anywhere]",
  {
    variants: {
      size: {
        sm: "h-7 px-2 text-caption",
        md: "h-8 px-2.5 text-caption",
      },
      tone: {
        neutral: cn(
          pillRadiusClass,
          "bg-muted text-foreground",
        ),
        commerceAmber: cn(
          pillRadiusClass,
          "bg-amber-500/15 text-amber-900 dark:bg-amber-400/15 dark:text-amber-100",
        ),
        commerceEmerald: cn(
          pillRadiusClass,
          "bg-emerald-600/12 text-emerald-800 dark:bg-emerald-400/15 dark:text-emerald-200",
        ),
        commerceRed: cn(
          pillRadiusClass,
          "bg-red-600/12 text-red-800 dark:bg-red-400/15 dark:text-red-200",
        ),
        overlay: cn(
          "rounded-2xl border border-white/20 bg-background/95 text-foreground shadow-sm",
        ),
        overlayDark: cn(
          "rounded-2xl border border-white/15 bg-black/70 text-white shadow-sm",
        ),
        overlayStatusSold: cn(
          "rounded-2xl border border-red-900/30 bg-red-600 font-semibold uppercase tracking-wide text-white",
        ),
        overlayStatusReserved: cn(
          "rounded-2xl border border-amber-900/30 bg-amber-500 font-semibold uppercase tracking-wide text-white",
        ),
        brand: cn(
          pillRadiusClass,
          "border border-brand/30 bg-brand/10 text-brand dark:text-brand",
        ),
      },
    },
    defaultVariants: {
      size: "md",
      tone: "neutral",
    },
  },
);

function ListingChip({
  className,
  size,
  tone,
  ...props
}: React.ComponentProps<"span"> & VariantProps<typeof listingChipVariants>) {
  return (
    <span
      data-slot="listing-chip"
      className={cn(listingChipVariants({ size, tone }), className)}
      {...props}
    />
  );
}

export { ListingChip, listingChipVariants };
