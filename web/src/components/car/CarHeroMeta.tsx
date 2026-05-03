import { CalendarDays, Fuel, Gauge, IdCard } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { MotionStagger, MotionStaggerItem } from "@/components/ui/motion";
import { CarPricingTierBadge } from "@/components/car/CarPricingTierBadge";
import { asStr, formatKm, formatRegYearMonth, normalizeFuelLabel, translateKoToRuText } from "@/lib/car-detail-data";
import { type CarListingAvailability, carSourceDisplayName } from "@/lib/car-listing-trust";
import { extractPricingTier } from "@/lib/pricing-tier-ui";

/** Заголовок и ключевые факты под галереей (чипы с иконками — как у крупных площадок). */
export function CarHeroMeta({
  title,
  data,
  sourceLabel,
  availability = "available",
}: {
  title: string;
  data: Record<string, unknown>;
  sourceLabel?: string | null;
  availability?: CarListingAvailability;
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
  const fuelLabel = normalizeFuelLabel(fuel);
  if (fuelLabel) chips.push({ key: "fuel", label: fuelLabel, icon: Fuel });
  const hp = asStr(data.power_kwhp) ?? asStr(data.power) ?? asStr(data.hp);
  if (hp) chips.push({ key: "hp", label: `${translateKoToRuText(hp)} л.с.`, icon: Gauge });
  const displacement = asStr(data.displacement) ?? asStr(data.engine_displacement);
  if (displacement) chips.push({ key: "cc", label: `${translateKoToRuText(displacement)} см3`, icon: Fuel });
  const plate = asStr(data.vehicle_no) ?? asStr(data.car_no);
  if (plate) chips.push({ key: "plate", label: `Гос № ${plate}`, variant: "secondary", icon: IdCard });

  const srcHuman = sourceLabel ? carSourceDisplayName(sourceLabel) : null;
  const pricingTier = extractPricingTier(data);

  return (
    <header className="mt-6 min-w-0 border-b border-border/60 pb-8 sm:mt-8">
      {srcHuman ? (
        <p className="mb-2 break-words text-xs font-medium text-muted-foreground [overflow-wrap:anywhere]">
          Источник · <span className="text-foreground">{srcHuman}</span>
        </p>
      ) : null}
      {availability === "sold" ? (
        <p className="mb-2 inline-flex rounded-full border border-red-900/35 bg-red-950/20 px-3 py-1 text-xs font-semibold text-red-800 dark:text-red-200">
          Продан — скоро уберём из каталога
        </p>
      ) : availability === "reserved" ? (
        <p className="mb-2 inline-flex rounded-full border border-amber-700/40 bg-amber-500/15 px-3 py-1 text-xs font-semibold text-amber-950 dark:text-amber-100">
          Зарезервировано на площадке
        </p>
      ) : null}
      <h1 className="font-heading text-[1.55rem] font-bold leading-snug tracking-tight text-foreground [overflow-wrap:anywhere] sm:text-3xl md:text-[2.15rem]">
        {title}
      </h1>
      {pricingTier ? (
        <div className="mt-3 flex flex-wrap gap-2">
          <CarPricingTierBadge tier={pricingTier} />
        </div>
      ) : null}
      {chips.length > 0 ? (
        <MotionStagger className="mt-4 flex min-w-0 flex-wrap gap-2" aria-label="Краткие характеристики">
          {chips.map((c) => {
            const Icon = c.icon;
            return (
              <MotionStaggerItem key={c.key} className="min-w-0 max-w-full">
                <Badge
                  variant={c.variant === "secondary" ? "secondary" : "outline"}
                  className="inline-flex h-auto w-full max-w-full items-start gap-1.5 rounded-2xl border-border/70 py-2 ps-2.5 pe-3 text-left text-xs font-medium normal-case shadow-sm sm:inline-flex sm:w-auto sm:max-w-none sm:rounded-full sm:items-center"
                >
                  <Icon className="mt-0.5 size-3.5 shrink-0 opacity-80 sm:mt-0" aria-hidden />
                  <span className="min-w-0 flex-1 [overflow-wrap:anywhere]">{c.label}</span>
                </Badge>
              </MotionStaggerItem>
            );
          })}
        </MotionStagger>
      ) : null}
    </header>
  );
}
