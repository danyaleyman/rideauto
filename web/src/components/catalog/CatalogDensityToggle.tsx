"use client";

import { useMemo } from "react";
import { ChevronsUpDown, LayoutGrid, List, Table2 } from "lucide-react";
import { useLocaleContext } from "@/components/LocaleProvider";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { cn } from "@/lib/utils";
import type { CatalogDensity } from "@/lib/catalog-density";

const VIEW_ICONS = {
  list: List,
  tile: LayoutGrid,
  table: Table2,
} as const;

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
        { id: "list" as const, label: t("catalog.view.list"), desktopOnly: false },
        { id: "tile" as const, label: t("catalog.view.tile"), desktopOnly: false },
        { id: "table" as const, label: t("catalog.view.table"), desktopOnly: true },
      ] as const,
    [t],
  );
  const active = options.find((o) => o.id === value) ?? options[0];
  const ActiveIcon = VIEW_ICONS[active.id];

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          type="button"
          variant="outline"
          data-testid="catalog-view-toggle"
          className={cn("h-10 min-w-0 max-w-[11rem] shrink justify-between px-3 font-normal", className)}
          aria-label={t("catalog.view.aria")}
        >
          <span className="flex min-w-0 items-center gap-2">
            <ActiveIcon className="size-4 shrink-0 opacity-70" aria-hidden />
            <span className="min-w-0 truncate text-start">{active.label}</span>
          </span>
          <ChevronsUpDown className="size-4 shrink-0 opacity-55" aria-hidden />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent
        align="end"
        className="w-[var(--radix-dropdown-menu-trigger-width)] min-w-[13rem] p-1.5"
      >
        <DropdownMenuLabel>{t("catalog.view.aria")}</DropdownMenuLabel>
        <DropdownMenuRadioGroup value={value} onValueChange={(next) => onChange(next as CatalogDensity)}>
          {options.map((opt) => {
            const Icon = VIEW_ICONS[opt.id];
            return (
              <DropdownMenuRadioItem
                key={opt.id}
                value={opt.id}
                data-testid={`catalog-view-${opt.id}`}
                className={cn("cursor-pointer", opt.desktopOnly && "hidden lg:flex")}
              >
                <Icon className="size-4 shrink-0 opacity-70" aria-hidden />
                {opt.label}
              </DropdownMenuRadioItem>
            );
          })}
        </DropdownMenuRadioGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
