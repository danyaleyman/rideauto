export type LotCalcEngine = "petrol" | "diesel" | "electric" | "hybrid";
export type LotCalcHybrid = "none" | "parallel" | "series";
export type LotCalcCurrency = "USD" | "EUR" | "JPY" | "KRW" | "CNY";
export type LotCalcAge = "0-3" | "3-5" | "5+";

export type LotBuyCalculatorPreset = {
  engineType: LotCalcEngine;
  hybridType: LotCalcHybrid;
  currency: LotCalcCurrency;
  price: string;
  volume: string;
  hpSingle: string;
  hpIce: string;
  hpEd: string;
  ageRange: LotCalcAge;
};

function num(v: unknown): number | null {
  if (typeof v === "number" && Number.isFinite(v)) return v;
  if (typeof v === "string" && v.trim()) {
    const n = Number(v.replace(/\s/g, "").replace(",", "."));
    return Number.isFinite(n) ? n : null;
  }
  return null;
}

function engineFromData(data: Record<string, unknown>): LotCalcEngine {
  const blob = [data.engine_type, data.engine_type_ru, data.fuel_type, data.fuel]
    .map((x) => String(x ?? "").toLowerCase())
    .join(" ");
  if (/гибрид|hybrid|phev|hev|하이브리드/.test(blob)) return "hybrid";
  if (/электро|electric|전기/.test(blob) && !/бенз|дизел|gasoline|diesel|가솔린|디젤/.test(blob)) {
    return "electric";
  }
  if (/дизел|diesel|디젤/.test(blob)) return "diesel";
  return "petrol";
}

function hybridFromData(data: Record<string, unknown>): LotCalcHybrid {
  const layout = String(data.hybrid_layout ?? "").toLowerCase();
  if (layout === "series") return "series";
  if (engineFromData(data) === "hybrid") return "parallel";
  return "none";
}

function currencyFromData(data: Record<string, unknown>): LotCalcCurrency {
  const source = String(data.source ?? "").toLowerCase();
  if (source.includes("che168") || source.includes("china")) return "CNY";
  if (source.includes("encar") || source.includes("korea")) return "KRW";
  if (source.includes("autotrader") || source.includes("usa")) return "USD";
  if (num(data.price_cny)) return "CNY";
  if (num(data.price_won)) return "KRW";
  return "USD";
}

function sourcePrice(data: Record<string, unknown>, currency: LotCalcCurrency): string {
  if (currency === "KRW") {
    const won = num(data.price_won);
    if (won && won > 0) {
      // Encar кладёт цену в 만원 (499 → 4 990 000 ₩).
      const actual = won < 20_000 ? won * 10_000 : won;
      return String(Math.round(actual));
    }
  }
  if (currency === "CNY") {
    const cny = num(data.price_cny);
    if (cny && cny > 0) return String(Math.round(cny));
  }
  return "";
}

function volumeCc(data: Record<string, unknown>): string {
  const cc = num(data.displacement_cc);
  if (cc && cc > 200) return String(Math.round(cc));
  const liters = num(data.displacement) ?? num(data.displacement_liters);
  if (liters && liters > 0 && liters < 20) return String(Math.round(liters * 1000));
  if (liters && liters >= 200) return String(Math.round(liters));
  return "";
}

function parseYearMonth(data: Record<string, unknown>): { y: number; m: number } | null {
  const raw = data.yearMonth ?? data.year_month ?? data.yearname ?? data.regdate ?? data.year;
  if (typeof raw === "number" && raw >= 1980 && raw <= 2100) return { y: raw, m: 1 };
  if (typeof raw === "number" && raw >= 198001 && raw <= 210012) {
    const y = Math.floor(raw / 100);
    const m = raw % 100;
    if (m >= 1 && m <= 12) return { y, m };
  }
  const s = String(raw ?? "").trim();
  const dash = s.match(/^(\d{4})[.\-](\d{1,2})/);
  if (dash) return { y: Number(dash[1]), m: Number(dash[2]) };
  const compact = s.replace(/\s/g, "").match(/^(\d{4})(\d{2})/);
  if (compact) {
    const m = Number(compact[2]);
    if (m >= 1 && m <= 12) return { y: Number(compact[1]), m };
  }
  const yearOnly = s.match(/^(\d{4})$/);
  if (yearOnly) return { y: Number(yearOnly[1]), m: 1 };
  return null;
}

function ageFromData(data: Record<string, unknown>): LotCalcAge {
  const ym = parseYearMonth(data);
  if (!ym) return "5+";
  const now = new Date();
  const months = (now.getFullYear() - ym.y) * 12 + (now.getMonth() + 1 - ym.m);
  const years = months / 12;
  if (years < 3) return "0-3";
  if (years < 5) return "3-5";
  return "5+";
}

export function lotBuyCalculatorPreset(data: Record<string, unknown>): LotBuyCalculatorPreset {
  const engineType = engineFromData(data);
  const currency = currencyFromData(data);
  const hp = num(data.power_hp) ?? num(data.hp) ?? num(data.power);
  const ice = num(data.power_ice_hp) ?? num(data.power_kwhp);
  const ed = num(data.power_electric_hp) ?? num(data.power_otherp);
  return {
    engineType,
    hybridType: hybridFromData(data),
    currency,
    price: sourcePrice(data, currency),
    volume: volumeCc(data),
    hpSingle: hp && engineType !== "hybrid" && engineType !== "electric" ? String(Math.round(hp)) : "",
    hpIce: ice ? String(Math.round(ice)) : hp && engineType === "hybrid" ? String(Math.round(hp)) : "",
    hpEd: ed ? String(Math.round(ed)) : "",
    ageRange: ageFromData(data),
  };
}
