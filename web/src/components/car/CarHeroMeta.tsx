import { CalendarDays, Fuel, Gauge, IdCard } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { MotionStagger, MotionStaggerItem } from "@/components/ui/motion";
import { CarPricingTierBadge } from "@/components/car/CarPricingTierBadge";
import { asStr, formatKm, normalizeFuelLabel, pickRegYearMonthDisplay, translateKoToRuText } from "@/lib/car-detail-data";
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
  const parseHp = (v: unknown): number | null => {
    const s = asStr(v);
    if (!s) return null;
    const tagged = /(\d{2,4})\s*(?:hp|ps|л\.?с\.?)/i.exec(s);
    if (tagged) return Number(tagged[1]);
    const plain = Number.parseInt(s.replace(/[^\d]/g, ""), 10);
    return Number.isFinite(plain) && plain > 0 ? plain : null;
  };
  const parseDisplacementCc = (v: unknown): number | null => {
    const s = asStr(v);
    if (!s) return null;
    const cc = /(\d{3,5})\s*(?:cc|см3|см³)/i.exec(s);
    if (cc) return Number(cc[1]);
    const liters = /(\d(?:[.,]\d)?)\s*(?:t|l)\b/i.exec(s);
    if (liters) {
      const n = Number(liters[1].replace(",", "."));
      if (Number.isFinite(n) && n > 0) return Math.round(n * 1000);
    }
    const plain = Number.parseInt(s.replace(/[^\d]/g, ""), 10);
    if (!Number.isFinite(plain) || plain <= 0) return null;
    // guard against "1.2T 116HP L4" -> 121164
    if (plain > 10000) return null;
    return plain;
  };
  type Chip = {
    key: string;
    label: string;
    variant?: "default" | "secondary";
    icon: typeof CalendarDays;
  };
  const chips: Chip[] = [];
  const y = pickRegYearMonthDisplay(data);
  if (y) chips.push({ key: "y", label: y, variant: "secondary", icon: CalendarDays });
  const km = formatKm(data.km_age);
  if (km) chips.push({ key: "km", label: km, icon: Gauge });
  const fuel = asStr(data.engine_type) ?? asStr(data.fuel);
  const fuelLabel = normalizeFuelLabel(fuel);
  if (fuelLabel) chips.push({ key: "fuel", label: fuelLabel, icon: Fuel });
  const hp =
    parseHp(data.power_hp) ?? parseHp(data.power_kwhp) ?? parseHp(data.power) ?? parseHp(data.hp);
  if (hp) chips.push({ key: "hp", label: `${hp} л.с.`, icon: Gauge });
  const displacementCc =
    parseDisplacementCc(data.displacement_cc) ??
    parseDisplacementCc(data.displacement) ??
    parseDisplacementCc(data.engine_displacement);
  if (displacementCc) chips.push({ key: "cc", label: `${displacementCc} см3`, icon: Fuel });
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
