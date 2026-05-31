/**
 * Русские подписи для КПП, привода и цвета (каталог, фильтры, карточка).
 */

import { asStr } from "@/lib/car-detail-data";

const CYRILLIC = /[а-яёА-ЯЁ]/;

const DRIVE_PHRASES: Array<{ re: RegExp; ru: string }> = [
  { re: /front[-\s]?wheel/i, ru: "Передний привод" },
  { re: /rear[-\s]?wheel/i, ru: "Задний привод" },
  { re: /all[-\s]?wheel|four[-\s]?wheel|4wd|awd|quattro|xdrive|4matic/i, ru: "Полный привод" },
  { re: /\bfwd\b/i, ru: "Передний привод" },
  { re: /\brwd\b/i, ru: "Задний привод" },
  { re: /\bawd\b/i, ru: "Полный привод" },
];

const DRIVE_EXACT: Record<string, string> = {
  fwd: "Передний привод",
  rwd: "Задний привод",
  awd: "Полный привод",
  "4wd": "Полный привод",
  前驱: "Передний привод",
  后驱: "Задний привод",
  四驱: "Полный привод",
  前置前驱: "Передний привод",
  前置四驱: "Полный привод",
  前置后驱: "Задний привод",
};

/** Che168 / Encar коды и синонимы → одна подпись на тип КПП. */
const TRANS_TYPE_CODES: Record<string, string> = {
  "1": "МКПП",
  "2": "АКПП",
  "3": "Вариатор (CVT)",
  "4": "Робот (DCT)",
  "5": "Роботизированная (AMT)",
  manual: "МКПП",
  automatic: "АКПП",
  cvt: "Вариатор (CVT)",
  dct: "Робот (DCT)",
  amt: "Роботизированная (AMT)",
  at: "АКПП",
  mt: "МКПП",
  "a/t": "АКПП",
  "m/t": "МКПП",
  手动: "МКПП",
  自动: "АКПП",
  双离合: "Робот (DCT)",
  无级变速: "Вариатор (CVT)",
};

const TRANS_ALIAS_TO_CANON: Record<string, string> = {
  механика: "МКПП",
  мкпп: "МКПП",
  автомат: "АКПП",
  акпп: "АКПП",
  вариатор: "Вариатор (CVT)",
  "вариатор (cvt)": "Вариатор (CVT)",
  "робот (dct)": "Робот (DCT)",
  "робот (двойное сцепление)": "Робот (DCT)",
  робот: "Робот (DCT)",
  "роботизированная (amt)": "Роботизированная (AMT)",
  "continuously variable transmission": "Вариатор (CVT)",
};

const COLOR_EXACT: Record<string, string> = {
  white: "Белый",
  black: "Чёрный",
  silver: "Серебристый",
  gray: "Серый",
  grey: "Серый",
  red: "Красный",
  blue: "Синий",
  green: "Зелёный",
  brown: "Коричневый",
  beige: "Бежевый",
  gold: "Золотой",
  orange: "Оранжевый",
  yellow: "Жёлтый",
  purple: "Фиолетовый",
  burgundy: "Бордовый",
  champagne: "Шампань",
  pearl: "Перламутр",
  白: "Белый",
  黑: "Чёрный",
  银: "Серебристый",
  灰: "Серый",
  红: "Красный",
  蓝: "Синий",
  绿: "Зелёный",
  棕: "Коричневый",
  金: "Золотой",
  黄: "Жёлтый",
};

function normKey(s: string): string {
  return s.trim().toLowerCase().replace(/\s+/g, " ");
}

function isCvtTransmissionText(raw: string): boolean {
  return /cvt|continuously\s*variable|simulated\s+\d+\s+gears|无级变速|无级/i.test(raw);
}

/**
 * Единая канонизация КПП для фильтров, каталога и карточки.
 * Сводит синонимы (Автомат/АКПП, Вариатор/CVT, «10» у Che168) к одной подписи.
 */
export function canonicalTransmissionRu(v: unknown): string | null {
  const raw = asStr(v);
  if (!raw) return null;

  if (isCvtTransmissionText(raw)) return "Вариатор (CVT)";

  const nk = normKey(raw);

  const steppedRu = nk.match(/^(\d{1,2})-ступенчатая$/);
  if (steppedRu) {
    if (steppedRu[1] === "10") return "Вариатор (CVT)";
    return `${steppedRu[1]}-ступенчатая`;
  }

  const alias = TRANS_ALIAS_TO_CANON[nk];
  if (alias) return alias;

  const typeCode = TRANS_TYPE_CODES[nk];
  if (typeCode) return typeCode;

  const mSpeed = raw.match(/^(\d{1,2})\s*[-]?\s*speed\b/i);
  if (mSpeed && !isCvtTransmissionText(raw)) return `${mSpeed[1]}-ступенчатая`;

  // Che168: gearbox=10 — «simulated 10 gears» у CVT, не 10-ступенчатый автомат.
  if (nk === "10") return "Вариатор (CVT)";

  if (/^[6-9]$/.test(nk)) return `${nk}-ступенчатая`;

  if (CYRILLIC.test(raw)) return TRANS_ALIAS_TO_CANON[nk] ?? raw;

  return raw;
}

/** Порядок в фильтре КПП. */
export function transmissionSortRank(label: string): number {
  const canon = canonicalTransmissionRu(label) ?? label;
  const nk = normKey(canon);
  if (nk === "мкпп") return 10;
  if (nk === "акпп") return 20;
  const stepped = nk.match(/^(\d{1,2})-ступенчатая$/);
  if (stepped) return 30 + Number(stepped[1]);
  if (nk.startsWith("вариатор")) return 50;
  if (nk.startsWith("робот (dct)")) return 60;
  if (nk.startsWith("роботизированная")) return 70;
  return 100;
}

export function displayDriveTypeRu(v: unknown): string | null {
  const raw = asStr(v);
  if (!raw) return null;
  if (CYRILLIC.test(raw)) return raw;
  const nk = normKey(raw);
  if (DRIVE_EXACT[nk] || DRIVE_EXACT[nk.replace(/[()]/g, "")]) {
    return DRIVE_EXACT[nk] ?? DRIVE_EXACT[nk.replace(/[()]/g, "")] ?? null;
  }
  for (const { re, ru } of DRIVE_PHRASES) {
    if (re.test(raw)) return ru;
  }
  const alnum = nk.replace(/[^a-z0-9]/g, "");
  if (DRIVE_EXACT[alnum]) return DRIVE_EXACT[alnum];
  return raw;
}

export function displayBodyTypeRu(v: unknown): string | null {
  const raw = asStr(v);
  if (!raw) return null;
  if (CYRILLIC.test(raw)) return raw;
  const nk = normKey(raw);
  const EXACT: Record<string, string> = {
    "passenger vehicle": "Легковой автомобиль",
    "pickup truck": "Пикап",
    truck: "Грузовик",
    suv: "Внедорожник (SUV)",
    mpv: "Минивэн / MPV",
    sedan: "Седан",
    hatchback: "Хэтчбек",
    coupe: "Купе",
    wagon: "Универсал",
    van: "Фургон / минивэн",
    convertible: "Кабриолет",
    crossover: "Кроссовер",
  };
  if (EXACT[nk]) return EXACT[nk];
  return raw;
}

export function displayTransmissionRu(v: unknown): string | null {
  return canonicalTransmissionRu(v);
}

export function displayColorRu(v: unknown): string | null {
  const raw = asStr(v);
  if (!raw) return null;
  if (CYRILLIC.test(raw)) return raw;
  const nk = normKey(raw);
  if (COLOR_EXACT[nk]) return COLOR_EXACT[nk];
  const first = nk.split(/[\s,/]+/)[0];
  if (first && COLOR_EXACT[first]) return COLOR_EXACT[first];
  if (nk.includes("pearl") && nk.includes("white")) return "Перламутровый белый";
  if (nk.includes("metallic")) return raw;
  if (/色/.test(raw) && raw.length <= 8) {
    if (raw.includes("白")) return "Белый";
    if (raw.includes("黑")) return "Чёрный";
    if (raw.includes("银")) return "Серебристый";
    if (raw.includes("灰")) return "Серый";
    if (raw.includes("红")) return "Красный";
    if (raw.includes("蓝")) return "Синий";
  }
  return raw;
}
