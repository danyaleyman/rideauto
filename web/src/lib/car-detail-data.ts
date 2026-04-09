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
