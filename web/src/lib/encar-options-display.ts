import { asStr } from "@/lib/car-detail-data";
import { ENCAR_OPTION_CODE_RU_TABLE } from "@/lib/encar-option-code-ru-table";

/** Пары «корейский фрагмент» → русский (длинные сначала). */
const KO_TO_RU: [string, string][] = [
  ["파노라마 선루프", "Панорамный люк"],
  ["파노라마 썬루프", "Панорамный люк"],
  ["선루프", "Люк в крыше"],
  ["썬루프", "Люк в крыше"],
  ["내비게이션", "Навигация"],
  ["네비게이션", "Навигация"],
  ["어라운드 뷰", "Кругобзорная камера"],
  ["어라운드뷰", "Кругобзорная камера"],
  ["후방 카메라", "Камера заднего вида"],
  ["전방 카메라", "Камера переднего вида"],
  ["스마트 크루즈", "Адаптивный круиз"],
  ["크루즈 컨트롤", "Круиз-контроль"],
  ["헤드업 디스플레이", "Проекция на лобовое стекло"],
  ["통풍 시트", "Вентиляция сидений"],
  ["열선 시트", "Подогрев сидений"],
  ["가죽 시트", "Кожаные сиденья"],
  ["가죽", "Кожа"],
  ["전동 시트", "Электрорегулировка сидений"],
  ["운전석 전동", "Электропривод водительского сиденья"],
  ["스마트키", "Смарт-ключ"],
  ["스마트 키", "Смарт-ключ"],
  ["원격시동", "Дистанционный запуск"],
  ["스포츠 패키지", "Спорт-пакет"],
  ["프리미엄 패키지", "Премиум-пакет"],
  ["컴포트 패키지", "Комфорт-пакет"],
  ["드라이브 와이즈", "Пакет Drive Wise"],
  ["하이패스", "Highway pass / автоплатёж"],
  ["전동 트렁크", "Электропривод крышки багажника"],
  ["전동 도어", "Электропривод двери"],
  ["LED 헤드램프", "Светодиодные фары"],
  ["HID", "Ксенон"],
  ["HID 헤드램프", "Ксеноновые фары"],
  ["알루미늄 휠", "Литые диски"],
  ["알루미늄휠", "Литые диски"],
  ["휠", "Диски"],
  ["오토 홀드", "Удержание Auto Hold"],
  ["전자 파킹", "Электрический стояночный тормоз"],
  ["스마트폰 무선충전", "Беспроводная зарядка телефона"],
  ["무선 충전", "Беспроводная зарядка"],
  ["공기청정", "Система очистки воздуха"],
  ["공조", "Климат-контроль"],
  ["듀얼 에어백", "Фронтальные подушки безопасности"],
  ["에어백", "Подушки безопасности"],
  ["ABS", "ABS"],
  ["ESC", "Стабилизация ESC"],
  ["차선이탈", "Контроль полосы"],
  ["차선 이탈", "Контроль полосы"],
];

function translateKoCarRough(s: string): string {
  let out = s;
  const pairs = [...KO_TO_RU].sort((a, b) => b[0].length - a[0].length);
  for (const [ko, ru] of pairs) {
    if (out.includes(ko)) out = out.split(ko).join(ru);
  }
  return out;
}

function normalizeOptionLabel(raw: string): string {
  const cleaned = translateKoCarRough(raw).replace(/\s{2,}/g, " ").trim();
  if (!cleaned) return "";
  // Иногда в данных приходит только числовой код вместо названия опции.
  if (/^\d{3,}$/.test(cleaned)) return "";
  return cleaned;
}

export function localizeEncarOptionText(raw: unknown): string | null {
  const s = asStr(raw);
  if (!s) return null;
  const translated = normalizeOptionLabel(s);
  return translated || null;
}

function collectPhotoRows(uniquePhotos: unknown, choicePhotos: unknown): unknown[] {
  const u = Array.isArray(uniquePhotos) ? uniquePhotos : [];
  const c = Array.isArray(choicePhotos) ? choicePhotos : [];
  return [...u, ...c];
}

/** Сопоставление кодов опций: 1, "1", "001", 001. */
export function optionCodesMatch(a: unknown, needle: string): boolean {
  const nb = needle.trim();
  if (!nb || nb === "null" || nb === "undefined") return false;
  if (a == null) return false;
  const na = String(a).trim();
  if (!na) return false;
  if (na === nb) return true;
  const stripA = na.replace(/^0+/, "") || "0";
  const stripB = nb.replace(/^0+/, "") || "0";
  if (stripA === stripB) return true;
  const numA = Number(na);
  const numB = Number(nb);
  if (Number.isFinite(numA) && Number.isFinite(numB) && numA === numB) return true;
  return false;
}

function lookupEncarStaticRu(code: string): string | undefined {
  const t = code.trim();
  if (!t) return undefined;
  const strip = t.replace(/^0+/, "") || "0";
  const n = Number.parseInt(t, 10);
  const asNum = Number.isFinite(n) ? String(n) : "";
  const pad3 = Number.isFinite(n) ? String(n).padStart(3, "0") : t;
  const pad2 = Number.isFinite(n) ? String(n).padStart(2, "0") : t;
  for (const k of [t, strip, asNum, pad3, pad2]) {
    if (k && ENCAR_OPTION_CODE_RU_TABLE[k]) return ENCAR_OPTION_CODE_RU_TABLE[k];
  }
  return undefined;
}

function hasOptionLikeFields(o: Record<string, unknown>): boolean {
  const code =
    o.optionCode ??
    o.code ??
    o.partCode ??
    o.optionId ??
    o.stdOptionId ??
    o.standardOptionId ??
    o.standard_option_id;
  const name = o.partName ?? o.name ?? o.optionName ?? o.title ?? o.optionTitle ?? o.displayName;
  return code != null && String(code).trim() !== "" && asStr(name) != null;
}

function deepCollectOptionRows(root: unknown, out: unknown[], seenJson: Set<string>, depth: number): void {
  if (depth > 18) return;
  if (root == null) return;
  if (Array.isArray(root)) {
    for (const el of root) deepCollectOptionRows(el, out, seenJson, depth + 1);
    return;
  }
  if (typeof root !== "object") return;
  const o = root as Record<string, unknown>;
  if (hasOptionLikeFields(o)) {
    try {
      const key = JSON.stringify(o);
      if (!seenJson.has(key)) {
        seenJson.add(key);
        out.push(o);
      }
    } catch {
      out.push(o);
    }
  }
  for (const v of Object.values(o)) {
    if (v && typeof v === "object") deepCollectOptionRows(v, out, seenJson, depth + 1);
  }
}

/** Все объекты с кодом+названием из sellingpoint, advertisementMasters и options. */
export function collectEncarOptionLabelRows(
  uniquePhotos: unknown,
  choicePhotos: unknown,
  extra: Record<string, unknown> | undefined,
  data: Record<string, unknown>,
): unknown[] {
  const out: unknown[] = [];
  const seen = new Set<string>();
  const pushDedupe = (row: unknown) => {
    if (!row || typeof row !== "object") return;
    try {
      const k = JSON.stringify(row);
      if (seen.has(k)) return;
      seen.add(k);
      out.push(row);
    } catch {
      out.push(row);
    }
  };
  for (const r of collectPhotoRows(uniquePhotos, choicePhotos)) pushDedupe(r);

  const sp = extra?.sellingpoint;
  if (sp && typeof sp === "object") deepCollectOptionRows(sp, out, seen, 0);

  const adv = extra?.advertisementMasters;
  if (adv != null) deepCollectOptionRows(adv, out, seen, 0);

  const opts = data.options;
  if (opts && typeof opts === "object") deepCollectOptionRows(opts, out, seen, 0);

  return out;
}

function codeFromOptionRow(item: unknown): string | null {
  if (!item || typeof item !== "object" || Array.isArray(item)) return null;
  const o = item as Record<string, unknown>;
  const raw =
    o.optionCode ??
    o.code ??
    o.partCode ??
    o.optionId ??
    o.stdOptionId ??
    o.standardOptionId ??
    o.standard_option_id;
  const s = asStr(raw);
  return s && s !== "null" && s !== "undefined" ? s : null;
}

function labelFromOptionRow(item: unknown): string | null {
  if (!item || typeof item !== "object" || Array.isArray(item)) return null;
  const o = item as Record<string, unknown>;
  const raw =
    asStr(o.partName) ??
    asStr(o.name) ??
    asStr(o.optionName) ??
    asStr(o.title) ??
    asStr(o.optionTitle) ??
    asStr(o.displayName);
  if (!raw) return null;
  const t = normalizeOptionLabel(raw);
  return t || null;
}

export function collectSelectedEncarOptions(
  uniquePhotos: unknown,
  choicePhotos: unknown,
  extra: Record<string, unknown> | undefined,
  data: Record<string, unknown>,
): Array<{ code: string | null; label: string }> {
  const rows = collectEncarOptionLabelRows(uniquePhotos, choicePhotos, extra, data);
  const out: Array<{ code: string | null; label: string }> = [];
  const seen = new Set<string>();
  for (const row of rows) {
    const label = labelFromOptionRow(row);
    if (!label) continue;
    const code = codeFromOptionRow(row);
    const key = `${(code || "").trim()}|${label.toLowerCase()}`;
    if (seen.has(key)) continue;
    seen.add(key);
    out.push({ code, label });
  }
  return out;
}

function nameFromOptionRows(code: string, rows: unknown[]): string | null {
  const cs = String(code).trim();
  for (const item of rows) {
    if (!item || typeof item !== "object" || Array.isArray(item)) continue;
    const o = item as Record<string, unknown>;
    const keys = [
      o.optionCode,
      o.code,
      o.partCode,
      o.optionId,
      o.stdOptionId,
      o.standardOptionId,
      o.standard_option_id,
    ];
    for (const oc of keys) {
      if (oc == null) continue;
      if (optionCodesMatch(oc, cs)) {
        return (
          asStr(o.partName) ??
          asStr(o.name) ??
          asStr(o.optionName) ??
          asStr(o.title) ??
          asStr(o.optionTitle) ??
          asStr(o.displayName)
        );
      }
    }
  }
  return null;
}

function normalizeOptionCode(code: unknown): string {
  if (typeof code === "string") return code.trim();
  if (typeof code === "number" && Number.isFinite(code)) return String(code);
  return JSON.stringify(code);
}

/** Подпись опции для блока «Комплектация»: фото/sellingpoint → статическая таблица → корейский текст → код. */
export function displayEncarStandardOption(
  code: unknown,
  uniquePhotos: unknown,
  choicePhotos: unknown,
  extra?: Record<string, unknown>,
  data?: Record<string, unknown>,
): string {
  const c = normalizeOptionCode(code);
  if (!c || c === "null" || c === "undefined") return "—";
  const rows = collectEncarOptionLabelRows(
    uniquePhotos,
    choicePhotos,
    extra,
    (data ?? {}) as Record<string, unknown>,
  );
  const fromPhotos = nameFromOptionRows(c, rows);
  if (fromPhotos) {
    const t = normalizeOptionLabel(fromPhotos);
    if (t) return t;
  }
  const fromStatic = lookupEncarStaticRu(c);
  if (fromStatic) return fromStatic;
  if (/[가-힣]/.test(c)) {
    const t = normalizeOptionLabel(c);
    if (t) return t;
  }
  return `Опция ${c}`;
}
