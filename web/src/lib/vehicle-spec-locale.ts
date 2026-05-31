import type { AppLocale } from "@/lib/i18n";
import {
  canonicalTransmissionRu,
  displayBodyTypeRu,
  displayColorRu,
  displayDriveTypeRu,
  displayTransmissionRu,
  transmissionSortRank,
} from "@/lib/vehicle-spec-ru";

/** Канон RU → EN для подписей характеристик. */
const SPEC_RU_TO_EN: Record<string, string> = {
  "Передний привод": "Front-wheel drive",
  "Задний привод": "Rear-wheel drive",
  "Полный привод": "All-wheel drive",
  МКПП: "Manual",
  АКПП: "Automatic",
  "Вариатор (CVT)": "CVT",
  "Робот (DCT)": "DCT",
  "Роботизированная (AMT)": "AMT",
  Белый: "White",
  Чёрный: "Black",
  Черный: "Black",
  Серебристый: "Silver",
  Серый: "Gray",
  Красный: "Red",
  Синий: "Blue",
  Зелёный: "Green",
  Зеленый: "Green",
  Коричневый: "Brown",
  Бежевый: "Beige",
  Золотой: "Gold",
  Оранжевый: "Orange",
  Жёлтый: "Yellow",
  Желтый: "Yellow",
  Фиолетовый: "Purple",
  Бордовый: "Burgundy",
  Шампань: "Champagne",
  Перламутр: "Pearl",
  "Перламутровый белый": "Pearl white",
  "Легковой автомобиль": "Passenger car",
  Пикап: "Pickup",
  Грузовик: "Truck",
  "Внедорожник (SUV)": "SUV",
  "Минивэн / MPV": "Minivan / MPV",
  Седан: "Sedan",
  Хэтчбек: "Hatchback",
  Купе: "Coupe",
  Универсал: "Wagon",
  "Фургон / минивэн": "Van / minivan",
  Кабриолет: "Convertible",
  Кроссовер: "Crossover",
};

function localizeSpec(locale: AppLocale, value: string | null): string | null {
  if (!value || locale === "ru") return value;
  if (SPEC_RU_TO_EN[value]) return SPEC_RU_TO_EN[value];
  const stepped = value.match(/^(\d{1,2})-ступенчатая$/);
  if (stepped) return `${stepped[1]}-speed automatic`;
  return value;
}

export function displayTransmission(locale: AppLocale, v: unknown): string | null {
  return localizeSpec(locale, displayTransmissionRu(v));
}

export function displayDriveType(locale: AppLocale, v: unknown): string | null {
  return localizeSpec(locale, displayDriveTypeRu(v));
}

export function displayBodyType(locale: AppLocale, v: unknown): string | null {
  return localizeSpec(locale, displayBodyTypeRu(v));
}

export function displayColor(locale: AppLocale, v: unknown): string | null {
  return localizeSpec(locale, displayColorRu(v));
}

export function canonicalTransmission(locale: AppLocale, v: unknown): string | null {
  return localizeSpec(locale, canonicalTransmissionRu(v));
}

export { transmissionSortRank };
