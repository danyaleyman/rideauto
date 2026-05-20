/**
 * Русские подписи для КПП, привода и цвета (каталог, фильтры, карточка).
 * Если значение уже на кириллице — возвращаем как есть.
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

const TRANS_EXACT: Record<string, string> = {
  "1": "МКПП",
  "2": "АКПП",
  "3": "Вариатор (CVT)",
  "4": "Робот (DCT)",
  "5": "Роботизированная (AMT)",
  "6": "6-ступенчатая",
  "7": "7-ступенчатая",
  "8": "8-ступенчатая",
  "9": "9-ступенчатая",
  manual: "МКПП",
  automatic: "АКПП",
  cvt: "Вариатор (CVT)",
  dct: "Робот (DCT)",
  amt: "Роботизированная (AMT)",
  at: "АКПП",
  mt: "МКПП",
  手动: "МКПП",
  自动: "АКПП",
  双离合: "Робот (DCT)",
  无级变速: "Вариатор (CVT)",
};

/** «8 at», «6speed», «9速» после normKey — сводим к «N-ступенчатая». */
const SPEED_GEAR_RE = /^(\d{1,2})\s*(?:at|speed|mt|dct|cvt|amt|速|挡|档)$/i;

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

/**
 * Каноничные подписи привода (в т.ч. FWD / «Front-Wheel Drive»).
 */
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

/**
 * Кузов: English / кит. → RU (каталог China, карточка).
 */
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

/**
 * КПП: коды API, English, «7-speed».
 */
export function displayTransmissionRu(v: unknown): string | null {
  const raw = asStr(v);
  if (!raw) return null;
  if (CYRILLIC.test(raw)) return raw;
  const nk = normKey(raw);
  if (TRANS_EXACT[nk]) return TRANS_EXACT[nk];
  if (/^\d{1,2}$/.test(nk) && TRANS_EXACT[nk]) return TRANS_EXACT[nk]!;

  if (nk === "continuously variable transmission") return "Вариатор";

  const mSpeed = raw.match(/^(\d{1,2})\s*[-]?\s*speed$/i);
  if (mSpeed) {
    const n = mSpeed[1];
    return `${n}-ступенчатая`;
  }
  const gearMatch = nk.match(SPEED_GEAR_RE);
  if (gearMatch) return `${gearMatch[1]}-ступенчатая`;
  // «1-speed DHT» и прочий текст — оставляем, но дожим по словам
  return raw;
}

/**
 * Цвет кузова: English / кит. иероглифы в короткие RU-имена.
 */
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
  // короткие китайские составные (白色 / 珍珠白)
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
