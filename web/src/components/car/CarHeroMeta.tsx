import { asStr, formatKm } from "@/lib/car-detail-data";

/** Заголовок и строка характеристик под галереей (в духе Encar). */
export function CarHeroMeta({
  title,
  data,
}: {
  title: string;
  data: Record<string, unknown>;
}) {
  const bits: string[] = [];
  const y = asStr(data.year) ?? asStr(data.yearMonth);
  if (y) bits.push(y);
  const km = formatKm(data.km_age);
  if (km) bits.push(km);
  const fuel = asStr(data.engine_type) ?? asStr(data.fuel);
  if (fuel) bits.push(fuel);
  const plate = asStr(data.vehicle_no) ?? asStr(data.car_no);
  if (plate) bits.push(`№ ${plate}`);

  return (
    <header className="mb-6 border-b border-border/80 pb-6">
      <h1 className="font-heading text-2xl font-bold tracking-tight text-foreground sm:text-3xl">{title}</h1>
      {bits.length > 0 ? (
        <p className="mt-3 text-sm leading-relaxed text-muted-foreground">{bits.join("  ·  ")}</p>
      ) : null}
    </header>
  );
}
