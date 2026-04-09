import { CalendarDays, Fuel, Gauge, IdCard } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { asStr, formatKm, formatRegYearMonth } from "@/lib/car-detail-data";

/** Заголовок и ключевые факты под галереей (чипы с иконками — как у крупных площадок). */
export function CarHeroMeta({
  title,
  data,
  sourceLabel,
}: {
  title: string;
  data: Record<string, unknown>;
  sourceLabel?: string | null;
}) {
  type Chip = {
    key: string;
    label: string;
    variant?: "default" | "secondary";
    icon: typeof CalendarDays;
  };
  const chips: Chip[] = [];
  const y =
    formatRegYearMonth(data.yearMonth) ??
    formatRegYearMonth(data.year) ??
    asStr(data.yearMonth) ??
    asStr(data.year);
  if (y) chips.push({ key: "y", label: y, variant: "secondary", icon: CalendarDays });
  const km = formatKm(data.km_age);
  if (km) chips.push({ key: "km", label: km, icon: Gauge });
  const fuel = asStr(data.engine_type) ?? asStr(data.fuel);
  if (fuel) chips.push({ key: "fuel", label: fuel, icon: Fuel });
  const plate = asStr(data.vehicle_no) ?? asStr(data.car_no);
  if (plate) chips.push({ key: "plate", label: `Гос № ${plate}`, variant: "secondary", icon: IdCard });

  return (
    <header className="mt-6 border-b border-border/60 pb-8 sm:mt-8">
      {sourceLabel ? (
        <p className="mb-2 text-xs font-medium text-muted-foreground">
          Объявление · <span className="text-foreground">{sourceLabel}</span>
        </p>
      ) : null}
      <h1 className="font-heading text-[1.65rem] font-bold leading-tight tracking-tight text-foreground sm:text-3xl md:text-[2.15rem]">
        {title}
      </h1>
      {chips.length > 0 ? (
        <ul className="mt-4 flex flex-wrap gap-2" aria-label="Краткие характеристики">
          {chips.map((c) => {
            const Icon = c.icon;
            return (
              <li key={c.key}>
                <Badge
                  variant={c.variant === "secondary" ? "secondary" : "outline"}
                  className="inline-flex h-auto max-w-full items-center gap-1.5 rounded-full border-border/70 py-1.5 ps-2 pe-3 text-xs font-medium normal-case shadow-sm"
                >
                  <Icon className="size-3.5 shrink-0 opacity-80" aria-hidden />
                  <span className="min-w-0 [overflow-wrap:anywhere]">{c.label}</span>
                </Badge>
              </li>
            );
          })}
        </ul>
      ) : null}
    </header>
  );
}
