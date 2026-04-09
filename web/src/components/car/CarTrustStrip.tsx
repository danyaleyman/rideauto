import { Check } from "lucide-react";

/** Статичный блок доверия под заголовком (без выдуманных фактов по авто). */
export function CarTrustStrip() {
  const items = [
    "Данные страницы — из проверенного объявления источника",
    "Полный расчёт доставки и таможни — у менеджера World Ride Auto",
    "Сопровождение сделки и постановка на учёт во Владивостоке",
  ];
  return (
    <div className="mb-8 rounded-2xl border border-border/80 bg-gradient-to-b from-card to-muted/20 p-4 shadow-sm ring-1 ring-border/40 sm:p-5">
      <ul className="space-y-2.5">
        {items.map((t) => (
          <li key={t} className="flex gap-2.5 text-sm text-foreground/90">
            <Check className="mt-0.5 size-4 shrink-0 text-emerald-600 dark:text-emerald-400" aria-hidden />
            <span className="leading-snug">{t}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
