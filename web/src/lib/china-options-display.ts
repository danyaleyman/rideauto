/** Перевод и фильтрация опций Che168 (EN/ZH) для блока «Комплектация». */

const EXACT_RU: Record<string, string> = {
  "Adaptive M Suspension": "Адаптивная M-подвеска",
  "M Sport Brakes": "M Sport тормоза",
  "Harman Kardon sound system": "Аудиосистема Harman Kardon",
  "Head-up display": "Проекционный дисплей",
  "Wireless charging": "Беспроводная зарядка",
  "Parking Assistant Plus": "Park Assistant Plus",
  "Heated steering wheel": "Подогрев руля",
  "Lumbar support": "Поясничная поддержка",
  "Adaptive cruise control": "Адаптивный круиз-контроль",
  "Surround view camera": "Камера 360°",
  "Panoramic sunroof": "Панорамная крыша",
  "Leather upholstery": "Кожаный салон",
  "Heated seats": "Подогрев сидений",
  "Ventilated seats": "Вентиляция сидений",
  "Massage seats": "Массаж сидений",
  "Keyless entry": "Бесключевой доступ",
  "Electric tailgate": "Электропривод багажника",
  "Blind spot monitoring": "Контроль слепых зон",
  "Lane keep assist": "Удержание в полосе",
  "Traffic sign recognition": "Распознавание знаков",
  "Sunroof": "Люк",
  "Cruise control": "Круиз-контроль",
  "Climate control": "Климат-контроль",
  "Navigation system": "Навигация",
  "Run-flat Tires": "Run-flat шины",
  "Tire pressure warning": "Контроль давления в шинах",
  "Tire Pressure Monitoring": "Контроль давления в шинах",
  "Seat Belt Reminder": "Напоминание о ремне безопасности",
  "Driver/Passenger Airbags": "Подушки безопасности водителя и пассажира",
  "Front/Rear Side Airbags": "Боковые подушки безопасности",
  "Front/Rear Curtain Airbags": "Шторки безопасности",
};

const PHRASE_RU: [RegExp, string][] = [
  [/passive safety/i, ""],
  [/active safety/i, ""],
  [/primary\s*●.*secondary/i, ""],
  [/front\s*●\s*\/\s*rear/i, ""],
  [/front\s*\/\s*rear\s*-\s*$/i, ""],
  [/front row/i, ""],
  [/color\s*\d+\s*colors?/i, ""],
  [/anti-?lock braking/i, "ABS (антиблокировочная система)"],
  [/abs\s*\(/i, "ABS"],
  [/electronic stability control/i, "Система стабилизации ESC"],
  [/traction control/i, "Противобуксовочная система"],
  [/brake force distribution/i, "Распределение тормозного усиления"],
  [/brake assist/i, "Помощь при экстренном торможении"],
  [/airbag/i, "Подушки безопасности"],
  [/sunroof/i, "Люк"],
  [/panoramic/i, "Панорамная крыша"],
  [/heated steering/i, "Подогрев руля"],
  [/heated seat/i, "Подогрев сидений"],
  [/ventilated seat/i, "Вентиляция сидений"],
  [/leather/i, "Кожаный салон"],
  [/blind spot/i, "Контроль слепых зон"],
  [/lane keep/i, "Удержание в полосе"],
  [/lane departure/i, "Предупреждение о смене полосы"],
  [/adaptive cruise/i, "Адаптивный круиз-контроль"],
  [/cruise control/i, "Круиз-контроль"],
  [/parking assist/i, "Парковочный ассистент"],
  [/rear view camera/i, "Камера заднего вида"],
  [/surround view/i, "Камера 360°"],
  [/360/i, "Камера 360°"],
  [/wireless charg/i, "Беспроводная зарядка"],
  [/head-?up display/i, "Проекционный дисплей"],
  [/navigation/i, "Навигация"],
  [/apple carplay/i, "Apple CarPlay"],
  [/android auto/i, "Android Auto"],
  [/bluetooth/i, "Bluetooth"],
  [/keyless/i, "Бесключевой доступ"],
  [/tire pressure/i, "Контроль давления в шинах"],
  [/run-?flat/i, "Run-flat шины"],
  [/seat belt/i, "Ремни безопасности"],
  [/curtain airbag/i, "Шторки безопасности"],
  [/side airbag/i, "Боковые подушки безопасности"],
  [/electric tailgate/i, "Электропривод багажника"],
  [/power tailgate/i, "Электропривод багажника"],
  [/memory seat/i, "Память сидений"],
  [/massage seat/i, "Массаж сидений"],
  [/rain sensor/i, "Датчик дождя"],
  [/auto hold/i, "Auto Hold"],
  [/auto dimming/i, "Автозатемнение зеркал"],
  [/led head/i, "Светодиодные фары"],
  [/xenon/i, "Ксеноновые фары"],
  [/fog lamp/i, "Противотуманные фары"],
];

const CATEGORY_HEADERS = new Set(
  [
    "passive safety",
    "active safety",
    "safety",
    "comfort",
    "exterior",
    "interior",
    "multimedia",
    "assist",
    "basic specifications",
    "high tech",
    "seats",
    "lights",
    "airbags",
  ].map((s) => s.toLowerCase()),
);

const CYRILLIC_RE = /[\u0400-\u04FF]/;

export function isChinaOptionNoise(label: string): boolean {
  const t = label.trim();
  if (!t) return true;
  if (/^\d+$/.test(t)) return true;
  if (/^[\W_]+$/.test(t)) return true;
  if (/[●◆▪]/.test(t)) return true;
  if (/^\s*(?:front|rear|primary|secondary|color)\b/i.test(t)) return true;
  if (/\b\d+\s+colors?\s*$/i.test(t)) return true;
  if (/primary\s*●|secondary\s*●|front\s*●\s*\/\s*rear/i.test(t)) return true;
  if (/^front\s*\/\s*rear\s*-?\s*$/i.test(t)) return true;
  const low = t.toLowerCase();
  if (CATEGORY_HEADERS.has(low)) return true;
  if (/^(passive|active)\s+safety$/i.test(t)) return true;
  return false;
}

export function displayChinaOptionRu(raw: string): string {
  const src = raw.trim();
  if (!src || isChinaOptionNoise(src)) return "";
  if (CYRILLIC_RE.test(src)) return src;

  const exact = EXACT_RU[src] ?? EXACT_RU[src.toLowerCase() as keyof typeof EXACT_RU];
  if (exact) return exact;

  let out = src;
  for (const [rx, repl] of PHRASE_RU) {
    if (rx.test(out)) {
      out = out.replace(rx, repl).replace(/\s+/g, " ").trim();
    }
  }
  out = out.replace(/\([^)]*\)/g, (m) => {
    const inner = m.slice(1, -1);
    if (/^(abs|ebd|cbc|eba|bas|ba|asr|tcs|trc|esc|esp|dsc|eba)$/i.test(inner.trim())) return "";
    return m;
  });
  out = out.replace(/\s+/g, " ").trim();
  if (!out || isChinaOptionNoise(out)) return "";
  if (!CYRILLIC_RE.test(out) && /^[a-z0-9\s/\-().]+$/i.test(out)) {
    const low = out.toLowerCase();
    if (CATEGORY_HEADERS.has(low)) return "";
  }
  return out;
}
