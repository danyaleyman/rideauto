"use client";

import { useMemo } from "react";
import { useLocaleContext } from "@/components/LocaleProvider";
import { cn } from "@/lib/utils";
import type { CatalogDensity } from "@/lib/catalog-density";
import { controlHeightClass } from "@/lib/design-system";

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
        "inline-flex shrink-0 items-center gap-0.5 rounded-lg bg-muted p-1",
        controlHeightClass,
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
            "h-full rounded-md px-3 text-xs font-medium transition-colors",
            value === opt.id
              ? "bg-background text-foreground shadow-sm"
              : "text-foreground/70 hover:text-foreground",
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
