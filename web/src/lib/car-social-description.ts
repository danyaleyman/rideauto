import {
  asStr,
  formatHumanDate,
  formatKm,
  normalizeFuelLabel,
  pickRegYearMonthDisplay,
} from "@/lib/car-detail-data";
import { getCarPageAbsoluteUrl } from "@/lib/car-url";
import { collectCarEquipmentLabels } from "@/lib/car-equipment-labels";
import { displayDriveTypeRu, displayTransmissionRu } from "@/lib/vehicle-spec-ru";
import { parseListingCalendarYear } from "@/lib/catalog-client-utils";

export type CarSocialDescriptionInput = {
  carId: string;
  title: string;
  data: Record<string, unknown>;
  priceRub: number | null;
  priceOnRequest?: boolean;
  publishedAt?: string | null;
};

function formatRubPlain(n: number): string {
  return `${Math.round(n).toLocaleString("ru-RU")} руб.`;
}

function parseHp(v: unknown): number | null {
  const s = asStr(v);
  if (!s) return null;
  const tagged = /(\d{2,4})\s*(?:hp|ps|л\.?с\.?|horsepower|马力)?/i.exec(s);
  if (tagged) {
    const n = Number(tagged[1]);
    return Number.isFinite(n) && n > 0 ? n : null;
  }
  const plain = Number.parseInt(s.replace(/[^\d]/g, ""), 10);
  return Number.isFinite(plain) && plain > 0 ? plain : null;
}

function pickInt(v: unknown): number | null {
  if (typeof v === "number" && Number.isFinite(v)) return Math.trunc(v);
  const s = asStr(v);
  if (!s) return null;
  const n = Number.parseInt(s.replace(/[^\d]/g, ""), 10);
  return Number.isFinite(n) ? n : null;
}

function formatReleaseDate(data: Record<string, unknown>): string | null {
  const ym = data.yearMonth ?? data.year_month ?? data.yearname ?? data.regdate;
  if (typeof ym === "number" && ym >= 199_001 && ym <= 2_039_12) {
    const year = Math.floor(ym / 100);
    const month = ym % 100;
    if (month >= 1 && month <= 12) {
      return `${year}.${String(month).padStart(2, "0")}`;
    }
  }
  const s = asStr(ym);
  if (s) {
    const dot = /^(\d{4})\.(\d{1,2})$/.exec(s.trim());
    if (dot) return `${dot[1]}.${dot[2].padStart(2, "0")}`;
    const iso = /^(\d{4})-(\d{2})/.exec(s.trim());
    if (iso) return `${iso[1]}.${iso[2]}`;
    const flat = /^(\d{4})(\d{2})/.exec(s.replace(/\s/g, ""));
    if (flat) return `${flat[1]}.${flat[2]}`;
  }
  const reg = pickRegYearMonthDisplay(data);
  if (reg) {
    const m = /^(\d{2})\/(\d{2})$/.exec(reg);
    if (m) {
      const year = parseListingCalendarYear(data.year) ?? 2000 + Number(m[1]);
      return `${year}.${m[2]}`;
    }
  }
  const y = parseListingCalendarYear(data.year);
  return y ? String(y) : null;
}

function litersFromDisplacement(data: Record<string, unknown>): string | null {
  const label = asStr(data.displacement_label) ?? asStr(data.displacement);
  if (label) {
    const m = /(\d+(?:\.\d+)?)\s*l/i.exec(label);
    if (m) return `${m[1]} л`;
    const ccInLabel = /(\d{3,5})\s*cc/i.exec(label);
    if (ccInLabel) {
      const liters = Number(ccInLabel[1]) / 1000;
      if (liters > 0 && liters < 20) return `${liters.toFixed(1).replace(/\.0$/, "")} л`;
    }
  }
  const cc = pickInt(data.displacement_cc);
  if (cc != null && cc > 0) {
    const liters = cc / 1000;
    return `${liters.toFixed(1).replace(/\.0$/, "")} л`;
  }
  return null;
}

function hasTurbo(data: Record<string, unknown>, title: string): boolean {
  const flags = [data.turbo, data.is_turbo, data.engine_turbo];
  if (flags.some((v) => v === true || v === 1 || v === "1")) return true;
  const blob = [
    title,
    asStr(data.generation),
    asStr(data.configuration),
    asStr(data.trim_name),
    asStr(data.displacement_label),
    asStr(data.displacement),
  ]
    .filter(Boolean)
    .join(" ");
  return /\b(turbo|турбо|tsi|tfsi|tgdi|gdi-t|1\.\d+t)\b/i.test(blob);
}

function formatEngineLine(data: Record<string, unknown>, title: string): string | null {
  const liters = litersFromDisplacement(data);
  const fuel = normalizeFuelLabel(data.engine_type);
  const turbo = hasTurbo(data, title);
  const parts: string[] = [];
  if (liters) parts.push(liters);
  if (fuel) parts.push(fuel.toLowerCase());
  if (turbo) parts.push("(турбо)");
  if (!parts.length) return fuel ? fuel : null;
  return parts.join(", ");
}

function formatPowerLine(data: Record<string, unknown>): string | null {
  const hp =
    parseHp(data.power_hp) ??
    parseHp(data.power) ??
    parseHp(data.hp) ??
    parseHp(data.power_kwhp);
  if (!hp) return null;
  const kw =
    pickInt(data.power_kw) ??
    (hp ? Math.round(hp * 0.7355) : null);
  if (kw) return `${hp} л.с. (${kw} кВт)`;
  return `${hp} л.с.`;
}

function formatTorqueLine(data: Record<string, unknown>): string | null {
  const nm = pickInt(data.torque_nm) ?? pickInt(data.max_torque_nm) ?? pickInt(data.torque);
  if (nm == null || nm <= 0) return null;
  return `${nm} Н·м`;
}

function formatDriveSocial(data: Record<string, unknown>): string | null {
  const raw =
    asStr(data.drive_type_ru) ??
    asStr(data.drive_type) ??
    asStr(data.drivemode) ??
    asStr(data.drivingmode);
  const mapped = raw ? displayDriveTypeRu(raw) ?? raw : null;
  const low = (mapped ?? "").toLowerCase();
  if (low.includes("перед")) return "передний — 2WD / FWD";
  if (low.includes("зад")) return "задний — RWD";
  if (low.includes("полн")) return "полный — 4WD / AWD";
  const r = (raw ?? "").toUpperCase();
  if (/\b(2WD|FWD|前驱)\b/.test(r)) return "передний — 2WD / FWD";
  if (/\b(RWD|后驱)\b/.test(r)) return "задний — RWD";
  if (/\b(4WD|AWD|四驱)\b/.test(r)) return "полный — 4WD / AWD";
  return mapped;
}

function formatTransmissionSocial(data: Record<string, unknown>): string | null {
  const raw =
    asStr(data.transmission_type_ru) ??
    asStr(data.transmission_type) ??
    asStr(data.gearbox) ??
    asStr(data.transmission);
  if (!raw) return null;
  const mapped = displayTransmissionRu(raw) ?? raw;
  const low = mapped.toLowerCase();
  if (low.includes("автомат") || low.includes("акпп") || low === "at") return "автоматическая";
  if (low.includes("механ") || low.includes("мкпп") || low === "mt") return "механическая";
  if (low.includes("вариатор") || low.includes("cvt")) return "вариатор";
  if (low.includes("робот") || low.includes("dct")) return "роботизированная";
  if (/[а-яё]/i.test(mapped)) {
    return mapped.charAt(0).toLowerCase() + mapped.slice(1);
  }
  return mapped;
}

function pickTrimName(data: Record<string, unknown>): string | null {
  return (
    asStr(data.trim_name) ??
    asStr(data.configuration) ??
    asStr(data.gradeName) ??
    asStr(data.trim)
  );
}

function publicationDateLabel(publishedAt?: string | null): string {
  const fromApi = publishedAt ? formatHumanDate(publishedAt) : null;
  if (fromApi) return fromApi;
  return new Intl.DateTimeFormat("ru-RU", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  }).format(new Date());
}

/** Текст объявления для соцсетей / мессенджеров. */
export function buildCarSocialDescription(input: CarSocialDescriptionInput): string {
  const { carId, title, data, priceRub, priceOnRequest, publishedAt } = input;
  const url = getCarPageAbsoluteUrl(carId);
  const lines: string[] = [`🚘 ${title} (${url})`, ""];

  const specs: Array<[string, string | null]> = [
    ["Двигатель", formatEngineLine(data, title)],
    ["Мощность", formatPowerLine(data)],
    ["Крутящий момент", formatTorqueLine(data)],
    ["Привод", formatDriveSocial(data)],
    ["Трансмиссия", formatTransmissionSocial(data)],
    ["Дата выпуска", formatReleaseDate(data)],
    ["Пробег", formatKm(data.km_age)],
  ];

  for (const [label, value] of specs) {
    if (value) lines.push(`• ${label}: ${value}`);
  }

  const trim = pickTrimName(data);
  const equipment = collectCarEquipmentLabels(data);
  if (trim || equipment.length) {
    lines.push("");
    if (trim) lines.push(`Комплектация ${trim}:`);
    else lines.push("Комплектация:");
    lines.push("");
    for (const item of equipment) {
      lines.push(`> ${item}`);
    }
  }

  lines.push("");
  if (!priceOnRequest && priceRub != null && !Number.isNaN(priceRub) && priceRub > 0) {
    lines.push(`💳 Цена во Владивостоке под ключ: ${formatRubPlain(priceRub)}`);
  } else {
    lines.push("💳 Цена во Владивостоке под ключ: по запросу");
  }
  lines.push("");
  lines.push(`Цена является актуальной на момент публикации — ${publicationDateLabel(publishedAt)}`);
  lines.push("...");

  return lines.join("\n");
}
