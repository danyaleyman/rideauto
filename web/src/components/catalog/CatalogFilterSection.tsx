"use client";

import type { ReactNode } from "react";
import type { LucideIcon } from "lucide-react";
import {
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { cn } from "@/lib/utils";

export function FilterSectionSummary({ text }: { text: string }) {
  if (!text) return null;
  return (
    <span className="mt-0.5 block truncate text-xs font-normal text-muted-foreground">{text}</span>
  );
}

export function FilterActiveBadge({ count }: { count: number }) {
  if (count <= 0) return null;
  return (
    <span className="ms-2 inline-flex min-h-5 min-w-5 shrink-0 items-center justify-center rounded-full bg-primary px-1.5 text-[10px] font-semibold tabular-nums text-primary-foreground">
      {count > 9 ? "9+" : count}
    </span>
  );
}

/**
 * Секция фильтров в мобильном аккордеоне.
 */
export function CatalogFilterAccordionSection({
  value,
  icon: Icon,
  title,
  hint: _hint,
  summary,
  activeCount = 0,
  children,
  className,
}: {
  value: string;
  icon?: LucideIcon;
  title: string;
  hint?: string;
  summary?: string;
  activeCount?: number;
  children: ReactNode;
  className?: string;
}) {
  void _hint;
  return (
    <AccordionItem value={value} className={cn("border-border", className)}>
      <AccordionTrigger className="py-3.5 ps-0 pe-8 hover:no-underline">
        <div className="min-w-0 flex-1 text-start">
          <div className="flex items-center gap-2">
            {Icon ? <Icon className="size-3.5 shrink-0 text-muted-foreground" aria-hidden /> : null}
            <span className="text-sm font-semibold leading-tight text-foreground">{title}</span>
            <FilterActiveBadge count={activeCount} />
          </div>
          {summary ? <FilterSectionSummary text={summary} /> : null}
        </div>
      </AccordionTrigger>
      <AccordionContent className="space-y-2.5 pb-4 pt-0.5">{children}</AccordionContent>
    </AccordionItem>
  );
}

/**
 * Секция фильтров в десктопном сайдбаре.
 * Иконка отображается рядом с заголовком.
 */
export function CatalogFilterFlatSection({
  icon: Icon,
  title,
  hint: _hint,
  summary,
  activeCount = 0,
  children,
  className,
}: {
  icon?: LucideIcon;
  title: string;
  hint?: string;
  summary?: string;
  activeCount?: number;
  children: ReactNode;
  className?: string;
}) {
  void _hint;
  return (
    <section className={cn("py-4", className)}>
      <div className="mb-2.5 flex items-center gap-2">
        {Icon ? <Icon className="size-3.5 shrink-0 text-muted-foreground" aria-hidden /> : null}
        <h3 className="text-sm font-semibold leading-tight">{title}</h3>
        <FilterActiveBadge count={activeCount} />
      </div>
      {summary ? <p className="-mt-1.5 mb-2.5 truncate text-xs text-muted-foreground">{summary}</p> : null}
      <div className="space-y-2.5">{children}</div>
    </section>
  );
}

