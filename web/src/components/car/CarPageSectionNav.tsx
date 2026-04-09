"use client";

import { cn } from "@/lib/utils";

const btn =
  "shrink-0 rounded-full border border-border/50 bg-muted/40 px-3.5 py-2 text-xs font-semibold text-muted-foreground shadow-sm transition-all hover:border-primary/30 hover:bg-background hover:text-foreground active:scale-[0.98]";

type Props = {
  hasDescription: boolean;
  hasSimilar: boolean;
};

/** Быстрый скролл по секциям — как на крупных карточках объявлений (моб. + десктоп). */
export function CarPageSectionNav({ hasDescription, hasSimilar }: Props) {
  const items: { id: string; label: string }[] = [];
  if (hasDescription) items.push({ id: "car-description", label: "Описание" });
  items.push({ id: "car-details", label: "Характеристики" });
  if (hasSimilar) items.push({ id: "car-similar", label: "Похожие" });

  if (items.length <= 1) return null;

  const go = (id: string) => {
    document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  return (
    <nav
      className={cn(
        "sticky top-14 z-20 -mx-4 mb-6 border-b border-border/50 bg-background/90 px-4 py-2.5 backdrop-blur-md",
        "sm:-mx-6 sm:px-6",
        "lg:top-[4.75rem] lg:mx-0 lg:mb-8 lg:rounded-2xl lg:border lg:border-border/55 lg:bg-card/95 lg:px-4 lg:py-3 lg:shadow-sm",
      )}
      aria-label="Разделы объявления"
    >
      <p className="mb-2 hidden text-[11px] font-semibold uppercase tracking-wider text-muted-foreground lg:block">
        На странице
      </p>
      <div className="flex gap-2 overflow-x-auto [-ms-overflow-style:none] [scrollbar-width:none] [&::-webkit-scrollbar]:hidden lg:flex-wrap">
        {items.map((it) => (
          <button key={it.id} type="button" onClick={() => go(it.id)} className={btn}>
            {it.label}
          </button>
        ))}
      </div>
    </nav>
  );
}
