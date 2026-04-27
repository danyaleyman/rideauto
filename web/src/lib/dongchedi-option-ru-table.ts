/**
 * Частые опции Dongchedi (китайский -> русский) для блока комплектации.
 * Словарь хранится в JSON, чтобы его удобно было расширять без правки кода.
 */

import DONGCHEDI_OPTION_RU_TABLE from "@/data/dongchedi-option-ru-table.json";

const UNKNOWN_OPTIONS_STORAGE_KEY = "wra:dongchedi:unknown-options";

function rememberUnknownOption(raw: string): void {
  if (typeof window === "undefined") return;
  try {
    const prevRaw = window.localStorage.getItem(UNKNOWN_OPTIONS_STORAGE_KEY);
    const parsed = prevRaw ? (JSON.parse(prevRaw) as unknown) : [];
    const prev = Array.isArray(parsed) ? parsed : [];
    const set = new Set(
      prev
        .map((x) => (typeof x === "string" ? x.trim() : ""))
        .filter(Boolean),
    );
    set.add(raw);
    const next = Array.from(set).sort((a, b) => a.localeCompare(b, "zh-CN")).slice(0, 1000);
    window.localStorage.setItem(UNKNOWN_OPTIONS_STORAGE_KEY, JSON.stringify(next));
  } catch {
    // ignore localStorage issues (private mode / quota / disabled)
  }
}

export function localizeDongchediOptionText(v: string): string {
  const s = (v || "").trim();
  if (!s) return "";
  const mapped = (DONGCHEDI_OPTION_RU_TABLE as Record<string, string>)[s];
  if (!mapped) rememberUnknownOption(s);
  return mapped || s;
}

export function getUnknownDongchediOptionsFromStorage(): string[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(UNKNOWN_OPTIONS_STORAGE_KEY);
    const arr = raw ? (JSON.parse(raw) as unknown) : [];
    if (!Array.isArray(arr)) return [];
    return arr.map((x) => (typeof x === "string" ? x.trim() : "")).filter(Boolean);
  } catch {
    return [];
  }
}
