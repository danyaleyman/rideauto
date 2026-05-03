import type { LucideIcon } from "lucide-react";
import { CalendarDays, Fuel, Gauge, Settings2, Zap } from "lucide-react";
import { extractCarImageUrls } from "@/lib/car-images";
import { imageUrlDedupeKey } from "@/lib/car-gallery-images";
import {
  asStr,
  formatKm,
  formatRegYearMonth,
  normalizeCatalogDisplayLabel,
  normalizeFuelLabel,
} from "@/lib/car-detail-data";
import type { Market } from "@/lib/catalog-url";
import type { FacetRow, SlimCar } from "@/lib/types";
import type { MouseEvent as ReactMouseEvent } from "react";

/** Номера страниц с «…» для shadcn Pagination. */
export function visiblePageItems(page: number, total: number): Array<number | "ellipsis"> {
  if (total < 1) return [];
  if (total === 1) return [1];
  const set = new Set<number>();
  set.add(1);
  set.add(total);
  for (let p = page - 1; p <= page + 1; p++) {
    if (p >= 1 && p <= total) set.add(p);
  }
  const sorted = [...set].sort((a, b) => a - b);
  const out: Array<number | "ellipsis"> = [];
  for (let i = 0; i < sorted.length; i++) {
    if (i > 0 && sorted[i] - sorted[i - 1] > 1) out.push("ellipsis");
    out.push(sorted[i]);
  }
  return out;
}

export function shouldShowPendingNavigation(e: ReactMouseEvent<HTMLAnchorElement>): boolean {
  return !(
    e.defaultPrevented ||
    e.button !== 0 ||
    e.metaKey ||
    e.ctrlKey ||
    e.shiftKey ||
    e.altKey
  );
}

export function previewImageUrls(car: SlimCar): string[] {
  const all = extractCarImageUrls((car.data ?? {}) as Record<string, unknown>);
  if (!all.length) return [];
  const seen = new Set<string>();
  const ordered: string[] = [];
  for (const u of all) {
    const t = u.trim();
    const k = imageUrlDedupeKey(t);
    if (seen.has(k)) continue;
    seen.add(k);
    ordered.push(t);
  }
  return ordered.slice(0, 4);
}

export function carsAddedTodayLabel(n: number): string {
  if (n === 0) return "Сегодня новых записей нет";
  const n10 = n % 10;
  const n100 = n % 100;
  let word: string;
  if (n100 >= 11 && n100 <= 19) word = "автомобилей";
  else if (n10 === 1) word = "автомобиль";
  else if (n10 >= 2 && n10 <= 4) word = "автомобиля";
  else word = "автомобилей";
  return `${n.toLocaleString("ru-RU")} ${word} добавлено сегодня`;
}

export type PassabilityStatus = "passable" | "young" | "old";

export function facetRowLabel(row: FacetRow): string {
  const label = String(row.label ?? "").trim();
  const normalized = normalizeCatalogDisplayLabel(label || row.value);
  return normalized || row.value;
}

export function groupFacetRows(
  rows: FacetRow[],
  opts?: { labelFormatter?: (row: FacetRow) => string; comparator?: (a: string, b: string) => number },
): Array<{ label: string; values: string[]; count: number }> {
  const grouped = new Map<string, { label: string; values: Set<string>; count: number }>();
  for (const row of rows) {
    const label = (opts?.labelFormatter ? opts.labelFormatter(row) : facetRowLabel(row)).trim();
    if (!label) continue;
    const key = label.toLowerCase().replace(/\s+/g, " ");
    const rawValues = Array.isArray(row.values) && row.values.length ? row.values : [row.value];
    const bucket = grouped.get(key) ?? { label, values: new Set<string>(), count: 0 };
    for (const v of rawValues) {
      const t = String(v ?? "").trim();
      if (t) bucket.values.add(t);
    }
    bucket.count += Number(row.count || 0);
    grouped.set(key, bucket);
  }
  const out = Array.from(grouped.values()).map((b) => ({
    label: b.label,
    values: Array.from(b.values),
    count: b.count,
  }));
  out.sort((a, b) => (opts?.comparator ? opts.comparator(a.label, b.label) : a.label.localeCompare(b.label)));
  return out;
}

export function parseYmValue(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) {
    const iv = Math.trunc(value);
    if (iv >= 190001 && iv % 100 >= 1 && iv % 100 <= 12) return iv;
  }
  const s = String(value ?? "").trim();
  if (!s) return null;
  const digits = s.replace(/[^\d]/g, "");
  if (digits.length < 6) return null;
  const y = Number.parseInt(digits.slice(0, 4), 10);
  const m = Number.parseInt(digits.slice(4, 6), 10);
  if (!Number.isFinite(y) || !Number.isFinite(m) || y <= 1900 || m < 1 || m > 12) return null;
  return y * 100 + m;
}

export function carPassabilityStatus(data: Record<string, unknown>): PassabilityStatus | null {
  const ym = parseYmValue(data.yearMonth) ?? parseYmValue(data.year_month) ?? parseYmValue(data.year);
  if (!ym) return null;
  const now = new Date();
  const nowYm = now.getUTCFullYear() * 100 + (now.getUTCMonth() + 1);
  const nowMonths = Math.floor(nowYm / 100) * 12 + (nowYm % 100 - 1);
  const carMonths = Math.floor(ym / 100) * 12 + (ym % 100 - 1);
  const ageMonths = nowMonths - carMonths;
  if (ageMonths <= 36) return "young";
  if (ageMonths <= 59) return "passable";
  return "old";
}

export function formatDisplacementLiters(cc: number): string {
  const liters = cc / 1000;
  const rounded = Math.round(liters * 10) / 10;
  const isInt = Math.abs(rounded - Math.round(rounded)) < 1e-9;
  const shown = isInt ? String(Math.round(rounded)) : String(rounded).replace(".", ",");
  const n = rounded;
  const last = Math.floor(n) % 10;
  const last2 = Math.floor(n) % 100;
  const word =
    !isInt
      ? "литра"
      : last === 1 && last2 !== 11
        ? "литр"
        : last >= 2 && last <= 4 && !(last2 >= 12 && last2 <= 14)
          ? "литра"
          : "литров";
  return `${shown} ${word}`;
}

export function catalogCardAttributeChips(
  data: Record<string, unknown>,
  yearNum?: number | null,
): { key: string; label: string; Icon: LucideIcon }[] {
  const chips: { key: string; label: string; Icon: LucideIcon }[] = [];
  const ym = formatRegYearMonth(data.yearMonth) ?? formatRegYearMonth(data.year);
  if (ym) chips.push({ key: "ym", label: ym, Icon: CalendarDays });
  else if (yearNum != null && Number.isFinite(yearNum) && yearNum > 0) {
    chips.push({ key: "y", label: String(Math.round(yearNum)), Icon: CalendarDays });
  }
  const km = formatKm(data.km_age);
  if (km) chips.push({ key: "km", label: km, Icon: Gauge });
  const fuel = asStr(data.engine_type) ?? asStr(data.fuel);
  const fuelLabel = normalizeFuelLabel(fuel);
  if (fuelLabel) chips.push({ key: "fuel", label: fuelLabel, Icon: Fuel });
  const normalizedFuelLower = (fuelLabel || "").toLowerCase();
  const isElectricFuel = normalizedFuelLower.startsWith("электро");
  const ccRaw = data.displacement ?? data.displacement_cc ?? data.engine_volume;
  const ccNum =
    typeof ccRaw === "number"
      ? Math.trunc(ccRaw)
      : Number.parseInt(String(ccRaw ?? "").replace(/[^\d]/g, ""), 10);
  if (!isElectricFuel && Number.isFinite(ccNum) && ccNum > 0) {
    chips.push({ key: "cc", label: formatDisplacementLiters(ccNum), Icon: Settings2 });
  }
  const hpRaw = data.power_hp ?? data.power ?? data.hp;
  const hpNum =
    typeof hpRaw === "number"
      ? Math.trunc(hpRaw)
      : Number.parseInt(String(hpRaw ?? "").replace(/[^\d]/g, ""), 10);
  if (Number.isFinite(hpNum) && hpNum > 0) {
    chips.push({ key: "hp", label: `${hpNum} л.с.`, Icon: Zap });
  }
  return chips;
}

export function cardOverlayBadges(
  data: Record<string, unknown>,
  yearNum?: number | null,
  market: Market = "korea",
): string[] {
  const out: string[] = [];
  if (yearNum && Number.isFinite(yearNum)) out.push(String(Math.trunc(yearNum)));
  if (market === "china") return out.slice(0, 1);
  return out.slice(0, 4);
}

export const COLOR_SWATCH_BY_NAME: Array<{ re: RegExp; className: string }> = [
  { re: /(бел|white)/i, className: "bg-white ring-1 ring-border" },
  { re: /(черн|black)/i, className: "bg-zinc-900 ring-1 ring-zinc-700" },
  { re: /(сер|gray|grey|silver|сереб)/i, className: "bg-zinc-400" },
  { re: /(син|blue)/i, className: "bg-blue-500" },
  { re: /(крас|red)/i, className: "bg-red-500" },
  { re: /(зелен|green)/i, className: "bg-emerald-500" },
  { re: /(желт|gold|orange|оранж)/i, className: "bg-amber-400" },
  { re: /(корич|brown|beige|беж)/i, className: "bg-amber-700" },
  { re: /(фиолет|purple|violet)/i, className: "bg-violet-500" },
];

export function colorSwatchClass(colorName: string): string {
  const match = COLOR_SWATCH_BY_NAME.find((item) => item.re.test(colorName));
  return match?.className ?? "bg-gradient-to-br from-slate-200 to-slate-500";
}

/** Человекочитаемое пояснение к ошибке сети/API для каталога. */
export function catalogSearchErrorHint(message: string): string {
  const m = message.toLowerCase();
  if (m.includes("failed to fetch") || m.includes("networkerror") || m === "typeerror: failed to fetch") {
    return "Похоже, нет соединения с сервером или сеть нестабильна.";
  }
  if (m.includes("таймаут") || m.includes("timeout") || m.includes("время ожидания")) {
    return "Запрос занял слишком много времени. Проверьте сеть и попробуйте снова.";
  }
  if (/\b52\d\b/.test(m) || m.includes("502") || m.includes("503") || m.includes("504")) {
    return "Сервер временно перегружен. Попробуйте через минуту.";
  }
  return "";
}
