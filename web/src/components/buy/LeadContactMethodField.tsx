"use client";

import { ChevronsUpDown } from "lucide-react";
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
import { LEAD_CONTACT_OPTIONS, type LeadContactMethodValue } from "@/lib/lead-contact-options";

type Props = {
  id: string;
  value: LeadContactMethodValue | string;
  onChange: (value: LeadContactMethodValue) => void;
  disabled?: boolean;
};

export function LeadContactMethodField({ id, value, onChange, disabled }: Props) {
  const active = LEAD_CONTACT_OPTIONS.find((o) => o.value === value) ?? LEAD_CONTACT_OPTIONS[0];
  return (
    <div className="grid gap-2">
      <Label htmlFor={id}>Предпочтительный способ связи</Label>
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
          <DropdownMenuLabel className="text-xs font-normal text-muted-foreground">Как с вами связаться</DropdownMenuLabel>
          <DropdownMenuRadioGroup
            value={active.value}
            onValueChange={(v) => onChange(v as LeadContactMethodValue)}
          >
            {LEAD_CONTACT_OPTIONS.map((o) => (
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
