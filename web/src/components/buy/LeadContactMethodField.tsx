"use client";

import { useMemo } from "react";
import { ChevronsUpDown } from "lucide-react";
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
import { Label } from "@/components/ui/label";
import { leadContactOptions, type LeadContactMethodValue } from "@/lib/lead-contact-options";

type Props = {
  id: string;
  value: LeadContactMethodValue | string;
  onChange: (value: LeadContactMethodValue) => void;
  disabled?: boolean;
};

export function LeadContactMethodField({ id, value, onChange, disabled }: Props) {
  const { t } = useLocaleContext();
  const options = useMemo(() => leadContactOptions(t), [t]);
  const active = options.find((o) => o.value === value) ?? options[0];
  return (
    <div className="grid gap-2">
      <Label htmlFor={id}>{t("buy.contactMethod")}</Label>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            id={id}
            type="button"
            variant="outline"
            disabled={disabled}
            className="h-11 w-full justify-between rounded-2xl font-normal"
            aria-haspopup="menu"
          >
            <span className="min-w-0 truncate text-start">{active.label}</span>
            <ChevronsUpDown className="size-4 shrink-0 opacity-50" aria-hidden />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="start" className="w-[var(--radix-dropdown-menu-trigger-width)] min-w-[12rem] p-1.5">
          <DropdownMenuLabel className="text-xs font-normal text-muted-foreground">
            {t("buy.contactMethodMenu")}
          </DropdownMenuLabel>
          <DropdownMenuRadioGroup
            value={active.value}
            onValueChange={(v) => onChange(v as LeadContactMethodValue)}
          >
            {options.map((o) => (
              <DropdownMenuRadioItem key={o.value} value={o.value} className="cursor-pointer rounded-xl">
                {o.label}
              </DropdownMenuRadioItem>
            ))}
          </DropdownMenuRadioGroup>
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  );
}
