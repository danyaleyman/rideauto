"use client";

import { useMemo } from "react";
import { useLocaleContext } from "@/components/LocaleProvider";
import { cn } from "@/lib/utils";
import type { CatalogDensity } from "@/lib/catalog-density";
import { controlHeightClass, pillRadiusClass } from "@/lib/design-system";

export function CatalogDensityToggle({
  value,
  onChange,
  className,
}: {
  value: CatalogDensity;
  onChange: (next: CatalogDensity) => void;
  className?: string;
}) {
  const { t } = useLocaleContext();
  const options = useMemo(
    () =>
      [
        { id: "comfortable" as const, label: t("catalog.density.comfortable") },
        { id: "compact" as const, label: t("catalog.density.compact") },
      ] as const,
    [t],
  );

  return (
    <div
      className={cn(
        "inline-flex shrink-0 items-center gap-0.5 border border-border/60 bg-muted/30 p-0.5",
        controlHeightClass,
        pillRadiusClass,
        className,
      )}
      role="group"
      aria-label={t("catalog.density.aria")}
    >
      {options.map((opt) => (
        <button
          key={opt.id}
          type="button"
          className={cn(
            "rounded-full px-3 text-xs font-medium transition-colors",
            value === opt.id
              ? "bg-background text-foreground shadow-sm ring-1 ring-elevated-ring"
              : "text-muted-foreground hover:text-foreground",
          )}
          aria-pressed={value === opt.id}
          onClick={() => onChange(opt.id)}
        >
          {opt.label}
        </button>
      ))}
    </div>
  );
}
