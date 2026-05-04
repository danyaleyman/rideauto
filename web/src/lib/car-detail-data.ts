/**
 * Безопасное чтение вложенных полей карточки из сырых `data` (корейский / китайский контур).
 */

import { formatPriceLabel } from "@/lib/format-price";
import fuelAliasData from "./fuel_label_aliases.json";

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

const CJK_RE = /[\u4e00-\u9fff\uac00-\ud7af]/;
const CHINA_HINT_RE =
  /\b(bao ma|ben chi|ao di|da zhong|ka di la ke|bao shi jie|gai kuan|liang qu|si qu|qian qu|hou qu|zeng cheng|kuan|ban|zhi zun|hao hua)\b/i;
const CHINA_SUBSTRING_FIXES: Array<[RegExp, string]> = [
  [/\bbao\s*ma\b/gi, "BMW"],
  [/\bben\s*chi\b/gi, "Mercedes-Benz"],
  [/\bao\s*di\b/gi, "Audi"],
  [/\bda\s*zhong\b/gi, "Volkswagen"],
  [/\bbao\s*shi\s*jie\b/gi, "Porsche"],
  [/\bka\s*di\s*la\s*ke\b/gi, "Cadillac"],
  [/\bji\s*li\b/gi, "Geely"],
  [/\bchang\s*an\b/gi, "Changan"],
];
const CHINA_TOKEN_FIXES: Array<[RegExp, string]> = [
  [/\bliang\s*qu\b/gi, "2WD"],
  [/\bsi\s*qu\b/gi, "4WD"],
  [/\bqian\s*qu\b/gi, "FWD"],
  [/\bhou\s*qu\b/gi, "RWD"],
  [/\bzeng\s*cheng\b/gi, "EREV"],
  [/\bgai\s*kuan\b/gi, "Facelift"],
  [/\bhao\s*hua\b/gi, "Luxury"],
  [/\bzhi\s*zun\b/gi, "Premium"],
  [/\bjin\s*kou\b/gi, "Import"],
];

function cleanupChinaNamePart(v: string, role: "mark" | "model" | "generation"): string {
  let s = v;
  for (const [rx, repl] of CHINA_SUBSTRING_FIXES) s = s.replace(rx, repl);
  for (const [rx, repl] of CHINA_TOKEN_FIXES) s = s.replace(rx, repl);
  s = s.replace(/[()[\]{}]+/g, " ").replace(CJK_RE, " ").replace(/\s+/g, " ").trim();
  s = s.replace(/^([A-Za-z0-9&-]+)\s+\1\b/i, "$1").trim();
  if (role === "model") {
    s = s.replace(/\b20\d{2}\b.*$/i, "").trim();
    s = s.replace(/\b\d(?:\.\d)?T\b.*$/i, "").trim();
    s = s.replace(/\b(2WD|4WD|FWD|RWD|EREV|Premium|Luxury|Facelift|Import)\b.*$/i, "").trim();
  }
  if (role === "generation") {
    s = s.replace(/^\d+\s+/, "").trim();
  }
  return s;
}

const KO_TO_RU_TERMS: [string, string][] = [
  ["동력조향 작동 오일 누유", "Подтекание масла ГУР"],
  ["실린더 커버(로커암 커버)", "Крышка ГБЦ (клапанная)"],
  ["실린더 헤드 / 개스킷", "ГБЦ / прокладка"],
  ["실린더 블록 / 오일팬", "Блок цилиндров / поддон"],
  ["워터펌프", "Водяной насос"],
  ["라디에이터", "Радиатор"],
  ["커먼레일", "Топливная рампа (Common Rail)"],
  ["추진축 및 베어링", "Кардан/приводной вал и подшипники"],
  ["추친축 및 베어링", "Кардан/приводной вал и подшипники"],
  ["디피렌셜 기어", "Дифференциал"],
  ["스티어링 펌프", "Насос ГУР"],
  ["스티어링 기어(MDPS포함)", "Рулевая рейка (вкл. MDPS)"],
  ["스티어링 조인트", "Рулевые шарниры"],
  ["파워고압호스", "Шланг высокого давления ГУР"],
  ["타이로드엔드 및 볼 조인트", "Наконечники тяг и шаровые"],
  ["브레이크 마스터 실린더오일 누유", "Подтекание ГТЦ"],
  ["브레이크 오일 누유", "Подтекание тормозной жидкости"],
  ["배력장치 상태", "Вакуумный усилитель тормозов"],
  ["작동상태", "Рабочее состояние"],
  ["양호", "Исправно"],
  ["없음", "Нет"],
  ["적정", "В норме"],
  ["자기진단", "Самодиагностика"],
  ["원동기", "Двигатель"],
  ["변속기", "Трансмиссия"],
  ["작동상태(공회전)", "Работа на холостом ходу"],
  ["오일누유", "Подтекание масла"],
  ["오일 유량", "Уровень масла"],
  ["냉각수누수", "Утечка охлаждающей жидкости"],
  ["냉각수 수량", "Уровень охлаждающей жидкости"],
  ["자동변속기(A/T)", "АКПП"],
  ["수동변속기(M/T)", "МКПП"],
  ["기어변속장치", "Механизм переключения передач"],
  ["오일유량 및 상태", "Уровень и состояние масла"],
  ["동력전달", "Привод"],
  ["클러치 어셈블리", "Сцепление"],
  ["등속조인트", "ШРУС"],
  ["조향", "Рулевое управление"],
  ["제동", "Тормозная система"],
  ["전기", "Электрика"],
  ["연료", "Топливная система"],
  ["연료누출(LP가스포함)", "Утечка топлива (вкл. LPG)"],
  ["발전기 출력", "Выход генератора"],
  ["시동 모터", "Стартер"],
  ["와이퍼 모터 기능", "Мотор стеклоочистителя"],
  ["실내송풍 모터", "Мотор вентилятора салона"],
  ["라디에이터 팬 모터", "Мотор вентилятора радиатора"],
  ["윈도우 모터", "Электростеклоподъемники"],
  ["고전원전기장치", "Высоковольтная система"],
  ["충전구 절연 상태", "Изоляция зарядного порта"],
  ["구동축전지 격리 상태", "Изоляция тяговой батареи"],
  ["고전원전기배선 상태(접속단자, 피복, 보호기구)", "Состояние ВВ-проводки"],
];

export function translateKoToRuText(v: string): string {
  let out = v.trim();
  if (!out) return out;
  const pairs = [...KO_TO_RU_TERMS].sort((a, b) => b[0].length - a[0].length);
  for (const [ko, ru] of pairs) {
    if (out.includes(ko)) out = out.split(ko).join(ru);
  }
  return out.replace(/\s{2,}/g, " ").trim();
}

function normFuelAliasKey(s: string): string {
  return s.trim().toLowerCase().replace(/\s+/g, " ");
}

const FUEL_TO_CANON_RU: Record<string, string> = (() => {
  const raw = (fuelAliasData as { to_canonical_ru?: Record<string, string> }).to_canonical_ru ?? {};
  const out: Record<string, string> = {};
  for (const [k, v] of Object.entries(raw)) {
    if (typeof v !== "string") continue;
    const canon = v.trim();
    const key = normFuelAliasKey(k);
    if (!key || !canon) continue;
    out[key] = canon;
  }
  return out;
})();

export function normalizeFuelLabel(v: unknown): string | null {
  const raw = asStr(v);
  if (!raw) return null;
  const ru = translateKoToRuText(raw).trim();
  const byRu = FUEL_TO_CANON_RU[normFuelAliasKey(ru)];
  if (byRu) return byRu;
  const byRaw = FUEL_TO_CANON_RU[normFuelAliasKey(raw)];
  return byRaw ?? ru;
}

/**
 * Если выбрано одно поколение, убираем совпадающие по токенам начала подписи комплектации
 * (дубль «2.5 GDI …» / разная транслитерация последних токенов не склеиваем — остаётся полная строка).
 */
export function trimFacetLabelMinusGeneration(trimRaw: string, generationDisplayRaw: string): string {
  const tl = trimRaw.trim();
  const gd = generationDisplayRaw.trim();
  if (!tl || !gd) return tl;
  const canonTrim = normalizeCatalogDisplayLabel(tl) ?? tl;
  const canonGen = normalizeCatalogDisplayLabel(gd) ?? gd;
  const aTok = canonTrim.trim().split(/\s+/).filter(Boolean);
  const bTok = canonGen.trim().split(/\s+/).filter(Boolean);
  let i = 0;
  while (
    i < aTok.length &&
    i < bTok.length &&
    aTok[i].toLowerCase() === bTok[i].toLowerCase()
  ) {
    i++;
  }
  if (i === 0) return tl;
  const rest = aTok.slice(i).join(" ").trim();
  return rest || tl;
}

export function normalizeCatalogDisplayLabel(v: unknown): string | null {
  const raw = asStr(v);
  if (!raw) return null;
  const translated = translateKoToRuText(raw);
  if (!translated) return null;
  // Last-resort cleanup for leaked Hangul values in facets/titles.
  const cleaned = translated.replace(/[\uac00-\ud7af]+/g, " ").replace(/\s{2,}/g, " ").trim();
  return cleaned || translated;
}

export function fuelSortRank(v: unknown): number {
  const label = normalizeFuelLabel(v)?.toLowerCase() ?? "";
  if (label === "бензин") return 1;
  if (label === "дизель") return 2;
  if (label.startsWith("гибрид (бензин)") || label.startsWith("бензин (")) return 3;
  if (label.startsWith("гибрид (дизель)") || label.startsWith("дизель (")) return 4;
  if (label === "электро" || label.startsWith("электро")) return 5;
  return 10;
}

export function cleanScalarText(v: unknown): string | null {
  const s = asStr(v);
  if (!s) return null;
  const t = s.trim();
  const low = t.toLowerCase();
  if (
    low === "null" ||
    low === "none" ||
    low === "undefined" ||
    low === "nan" ||
    low === "-" ||
    low === "—"
  ) {
    return null;
  }
  return t;
}

export function prettifyDataKey(key: string): string {
  const map: Record<string, string> = {
    mileage: "Пробег",
    carNo: "Госномер",
    inspName: "Станция инспекции",
    recordNo: "Номер записи",
    validityStartDate: "Начало гарантии",
    validityEndDate: "Окончание гарантии",
    firstRegistrationDate: "Первая регистрация",
    boardStateType: "Состояние кузова",
    carStateType: "Общее состояние",
    engineTransmission: "Двигатель и трансмиссия",
    simpleRepair: "Косметический ремонт",
    accident: "ДТП",
    accdient: "ДТП",
  };
  if (map[key]) return map[key];
  return key
    .replace(/[_-]+/g, " ")
    .replace(/([a-z])([A-Z])/g, "$1 $2")
    .replace(/\s+/g, " ")
    .trim()
    .replace(/^\p{L}/u, (s) => s.toUpperCase());
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

/** Зелёный / жёлтый / красный по ключевым корейским меткам статуса диагностики в карточке */
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

export function formatHumanDate(v: unknown): string | null {
  if (v == null || v === "") return null;
  const s = String(v).trim();
  const iso = /^(\d{4})-(\d{2})-(\d{2})/.exec(s);
  if (iso) return `${iso[3]}.${iso[2]}.${iso[1]}`;
  const flat = /^(\d{4})(\d{2})(\d{2})(?:\.0+)?$/.exec(s);
  if (flat) return `${flat[3]}.${flat[2]}.${flat[1]}`;
  const maybeTs = Date.parse(s);
  if (!Number.isNaN(maybeTs)) {
    return new Intl.DateTimeFormat("ru-RU", { day: "2-digit", month: "2-digit", year: "numeric" }).format(
      new Date(maybeTs),
    );
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

export function buildNormalizedCarTitle(
  mark: unknown,
  model: unknown,
  generation: unknown,
  source?: unknown,
): string | null {
  const markS = asStr(mark) ?? "";
  const modelS = asStr(model) ?? "";
  const genS = asStr(generation) ?? "";
  const sourceS = (asStr(source) ?? "").toLowerCase();
  const chinaLike =
    sourceS === "che168" ||
    sourceS === "china" ||
    [markS, modelS, genS].some((x) => CJK_RE.test(x) || CHINA_HINT_RE.test(x));
  if (!chinaLike) return joinUniqueSpecs(markS, modelS, genS);
  const m1 = cleanupChinaNamePart(markS, "mark");
  const m2 = cleanupChinaNamePart(modelS, "model");
  const m3 = cleanupChinaNamePart(genS, "generation");
  return joinUniqueSpecs(m1 || markS, m2 || modelS, m3 || genS);
}

/** Элементы осмотра (корейский контур): заголовок детали вместо сырого JSON. */
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
    const fd = formatHumanDate(date) ?? formatRegYearMonth(date) ?? asStr(date);
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
