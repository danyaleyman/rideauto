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

const KO_TO_RU_TERMS: [string, string][] = [
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
