/**
 * Безопасное чтение вложенных полей Encar / Dongchedi в `data` карточки.
 */

import { formatPriceLabel } from "@/lib/format-price";

export function getPath(obj: unknown, segments: string[]): unknown {
  let cur: unknown = obj;
  for (const s of segments) {
    if (cur == null || typeof cur !== "object" || Array.isArray(cur)) return undefined;
    cur = (cur as Record<string, unknown>)[s];
  }
  return cur;
}

export function asStr(v: unknown): string | null {
  if (v == null || v === "") return null;
  if (typeof v === "string") {
    const t = v.trim();
    return t || null;
  }
  if (typeof v === "number" && Number.isFinite(v)) return String(v);
  if (typeof v === "boolean") return v ? "Да" : "Нет";
  return null;
}

export function formatKm(v: unknown): string | null {
  if (v == null || v === "") return null;
  if (typeof v === "number" && Number.isFinite(v)) {
    return `${Math.round(v).toLocaleString("ru-RU")} км`;
  }
  if (typeof v === "string") {
    const n = Number(String(v).replace(/\s/g, "").replace(/км/gi, ""));
    if (!Number.isNaN(n)) return `${Math.round(n).toLocaleString("ru-RU")} км`;
    const t = v.trim();
    return t || null;
  }
  return null;
}

export function formatKrw(n: number | null | undefined): string {
  if (n == null || Number.isNaN(n)) return "—";
  return `${Math.round(n).toLocaleString("ru-RU")} ₩`;
}

export function formatRubFromUnknown(v: unknown): string | null {
  if (v == null || v === "") return null;
  const n = typeof v === "number" ? v : Number(String(v).replace(/\s/g, ""));
  if (Number.isNaN(n)) return null;
  return formatPriceLabel(n);
}

/** Зелёный / жёлтый / красный по ключевым корейским меткам статуса Encar-диагностики */
export function diagnosisStatusTone(title: string): "ok" | "warn" | "bad" | "neutral" {
  const t = title.toLowerCase();
  if (t.includes("양호") || t.includes("정상")) return "ok";
  if (t.includes("불량") || t.includes("교환") && t.includes("요망")) return "bad";
  if (t.includes("미세") || t.includes("누유") || t.includes("부족")) return "warn";
  return "neutral";
}

export function toneClass(tone: "ok" | "warn" | "bad" | "neutral"): string {
  switch (tone) {
    case "ok":
      return "border-emerald-500/40 bg-emerald-500/10 text-emerald-900 dark:text-emerald-100";
    case "warn":
      return "border-amber-500/40 bg-amber-500/10 text-amber-950 dark:text-amber-100";
    case "bad":
      return "border-red-500/40 bg-red-500/10 text-red-900 dark:text-red-100";
    default:
      return "border-border/60 bg-muted/50 text-muted-foreground";
  }
}

/** Пары ключ–значение из объекта (только скаляры и непустые). */
export function flatScalarRows(obj: unknown): [string, string][] {
  if (!obj || typeof obj !== "object" || Array.isArray(obj)) return [];
  const out: [string, string][] = [];
  for (const [k, v] of Object.entries(obj as Record<string, unknown>)) {
    if (v == null) continue;
    if (typeof v === "object") continue;
    const s = asStr(v);
    if (s) out.push([k, s]);
  }
  return out;
}

/** Регистрация в формате гг/мм (YY/MM). */
export function formatRegYearMonth(v: unknown): string | null {
  if (v == null || v === "") return null;
  const s = String(v).trim();
  const iso = /^(\d{4})-(\d{2})(?:-\d{2})?/.exec(s);
  if (iso) return `${iso[1].slice(2)}/${iso[2]}`;
  const ymFlat = /^(\d{4})(\d{2})(?:\.0+)?$/.exec(s.replace(/\s/g, ""));
  if (ymFlat) return `${ymFlat[1].slice(2)}/${ymFlat[2]}`;
  const n = typeof v === "number" ? v : Number(s.replace(/\s/g, ""));
  if (Number.isFinite(n) && n >= 199_001 && n <= 2_039_12) {
    const floor = Math.floor(n);
    const year = Math.floor(floor / 100);
    const month = floor % 100;
    if (month >= 1 && month <= 12) {
      return `${String(year).slice(2)}/${String(month).padStart(2, "0")}`;
    }
  }
  return null;
}

function uniqStrings(parts: unknown[]): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const p of parts) {
    const t = asStr(p);
    if (!t) continue;
    const key = t.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(t);
  }
  return out;
}

/** Марка · модель · … без повторяющихся одинаковых фрагментов. */
export function joinUniqueSpecs(...parts: unknown[]): string | null {
  const u = uniqStrings(parts);
  return u.length ? u.join(" · ") : null;
}

/** Элементы осмотра Encar: заголовок детали вместо сырого JSON. */
export function formatInspectionListItem(x: unknown): string {
  if (typeof x === "string" || typeof x === "number") return String(x);
  if (!x || typeof x !== "object") return JSON.stringify(x);
  const o = x as Record<string, unknown>;
  const title =
    asStr(o.title) ??
    asStr(o.name) ??
    asStr(o.partName) ??
    asStr(o.typeName) ??
    asStr(o.partTypeName);
  if (title) {
    const bits = [
      title,
      asStr(o.colorName),
      asStr(o.status),
      asStr(o.result),
      asStr(o.grade),
    ].filter(Boolean);
    return bits.join(" · ");
  }
  return JSON.stringify(x);
}

const HISTORY_SKIP_KEYS = new Set([
  "date",
  "changeDate",
  "regDate",
  "carNo",
  "plateNo",
  "vehicleNo",
]);

/** Смена номеров / строка истории: дата и госномер текстом, без JSON. */
export function formatCarHistoryObjectRow(obj: unknown): string {
  if (typeof obj === "string" || typeof obj === "number") return String(obj);
  if (!obj || typeof obj !== "object" || Array.isArray(obj)) return JSON.stringify(obj);
  const o = obj as Record<string, unknown>;
  const parts: string[] = [];
  const date = o.date ?? o.changeDate ?? o.regDate;
  if (date != null && date !== "") {
    const fd = formatRegYearMonth(date) ?? asStr(date);
    if (fd) parts.push(`Дата: ${fd}`);
  }
  const carNo = o.carNo ?? o.plateNo ?? o.vehicleNo;
  const pn = asStr(carNo);
  if (pn) parts.push(`Госномер: ${pn}`);
  for (const [k, v] of Object.entries(o)) {
    if (HISTORY_SKIP_KEYS.has(k)) continue;
    if (v == null || v === "") continue;
    if (typeof v === "object") continue;
    const sv = asStr(v);
    if (sv) parts.push(`${k}: ${sv}`);
  }
  if (parts.length) return parts.join(" · ");
  return JSON.stringify(o);
}
