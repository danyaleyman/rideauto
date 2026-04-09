"use client";

import { cn } from "@/lib/utils";

const btn =
  "max-w-full shrink-0 rounded-full border border-border/50 bg-muted/40 px-3 py-2 text-left text-xs font-semibold leading-snug text-muted-foreground shadow-sm transition-all [overflow-wrap:anywhere] hover:border-primary/30 hover:bg-background hover:text-foreground active:scale-[0.98] sm:px-3.5";

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
        "mb-6 w-full max-w-full rounded-2xl border border-border/55 bg-card/90 px-3 py-3 shadow-sm",
        "lg:sticky lg:top-[4.75rem] lg:z-20 lg:mb-8 lg:bg-card/95 lg:px-4 lg:backdrop-blur-sm",
      )}
      aria-label="Разделы объявления"
    >
      <p className="mb-2 hidden text-[11px] font-semibold uppercase tracking-wider text-muted-foreground lg:block">
        На странице
      </p>
      <div className="flex max-w-full flex-wrap gap-2">
        {items.map((it) => (
          <button key={it.id} type="button" onClick={() => go(it.id)} className={btn}>
            {it.label}
          </button>
        ))}
      </div>
    </nav>
  );
}
