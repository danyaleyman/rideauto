import type { SlimCar } from "@/lib/types";

/** Нормализация VIN для склейки дублей листингов Encar с разными ID. */
export function normalizeVinForCatalogDedupe(v: unknown): string {
  const s = String(v ?? "")
    .trim()
    .toUpperCase()
    .replace(/[\s-]/g, "");
  if (s.length < 11) return "";
  return s;
}

export function slimCarVin(car: SlimCar): string {
  const d = car.data as Record<string, unknown> | undefined;
  if (!d) return "";
  const raw = d.vin ?? d.VIN ?? d.vehicleIdentificationNumber;
  return normalizeVinForCatalogDedupe(raw);
}

function freshnessMs(car: SlimCar): number {
  const u = car.catalog_updated_at ? Date.parse(car.catalog_updated_at) : NaN;
  if (!Number.isNaN(u)) return u;
  const c = car.catalog_created_at ? Date.parse(car.catalog_created_at) : NaN;
  return Number.isNaN(c) ? 0 : c;
}

/** Оставляем один листинг на VIN (приоритет: новее catalog_updated_at, иначе catalog_created_at, затем меньший id). */
export function dedupeSlimCarsByVin(cars: SlimCar[]): SlimCar[] {
  if (cars.length < 2) return cars;

  function prefer(a: SlimCar, b: SlimCar): SlimCar {
    const ta = freshnessMs(a);
    const tb = freshnessMs(b);
    if (tb !== ta) return tb > ta ? b : a;
    return String(a.id).localeCompare(String(b.id), undefined, { numeric: true }) <= 0 ? a : b;
  }

  const bestByVin = new Map<string, SlimCar>();
  for (const c of cars) {
    const v = slimCarVin(c);
    if (!v) continue;
    const cur = bestByVin.get(v);
    if (!cur) bestByVin.set(v, c);
    else bestByVin.set(v, prefer(cur, c));
  }

  const placed = new Set<string>();
  const out: SlimCar[] = [];
  for (const c of cars) {
    const v = slimCarVin(c);
    if (!v) {
      out.push(c);
      continue;
    }
    if (placed.has(v)) continue;
    placed.add(v);
    out.push(bestByVin.get(v)!);
  }
  return out;
}
