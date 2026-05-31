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
    <span className="mt-1 block truncate text-xs font-normal text-primary/90">{text}</span>
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

export function CatalogFilterAccordionSection({
  value,
  icon: Icon,
  title,
  hint,
  summary,
  activeCount = 0,
  children,
  className,
}: {
  value: string;
  icon: LucideIcon;
  title: string;
  hint?: string;
  summary?: string;
  activeCount?: number;
  children: ReactNode;
  className?: string;
}) {
  return (
    <AccordionItem value={value} className={cn("border-border/50", className)}>
      <AccordionTrigger className="py-3.5 hover:bg-muted/30 sm:ps-4 sm:pe-11">
        <div className="flex min-w-0 flex-1 items-start gap-3 text-start">
          <span className="mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary">
            <Icon className="size-4" aria-hidden />
          </span>
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-0.5">
              <span className="font-semibold leading-tight text-foreground">{title}</span>
              <FilterActiveBadge count={activeCount} />
            </div>
            {hint && !summary ? (
              <p className="mt-0.5 text-xs font-normal leading-snug text-muted-foreground">{hint}</p>
            ) : null}
            {summary ? <FilterSectionSummary text={summary} /> : null}
          </div>
        </div>
      </AccordionTrigger>
      <AccordionContent className="space-y-3 border-t border-border/40 bg-muted/5 pb-4 pt-3 sm:px-4">
        {children}
      </AccordionContent>
    </AccordionItem>
  );
}

export function CatalogFilterFlatSection({
  icon: Icon,
  title,
  hint,
  summary,
  activeCount = 0,
  children,
  className,
}: {
  icon: LucideIcon;
  title: string;
  hint?: string;
  summary?: string;
  activeCount?: number;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section
      className={cn(
        "rounded-2xl border border-border/70 bg-card/50 shadow-sm ring-1 ring-border/30",
        className,
      )}
    >
      <div className="flex items-start gap-3 border-b border-border/50 px-4 py-3.5">
        <span className="flex size-8 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary">
          <Icon className="size-4" aria-hidden />
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-0.5">
            <h3 className="text-sm font-semibold leading-tight">{title}</h3>
            <FilterActiveBadge count={activeCount} />
          </div>
          {hint && !summary ? (
            <p className="mt-0.5 text-xs leading-snug text-muted-foreground">{hint}</p>
          ) : null}
          {summary ? <FilterSectionSummary text={summary} /> : null}
        </div>
      </div>
      <div className="space-y-3 px-4 py-3.5">{children}</div>
    </section>
  );
}
