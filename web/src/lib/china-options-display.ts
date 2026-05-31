/** Перевод, фильтрация и группировка опций Che168 (EN/ZH) для блока «Комплектация». */

export type ChinaOptionGroup = "assist" | "interior" | "safety" | "comfort" | "media" | "other";

const CYRILLIC_RE = /[\u0400-\u04FF]/;

function normKey(s: string): string {
  return s.trim().toLowerCase().replace(/[\s\-_:/()（）[\]【】.+,]+/g, "");
}

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
    "driving & handling",
    "driving and handling",
    "driving hardware",
    "driving functions",
    "exterior & anti-theft",
    "exterior and anti-theft",
    "exterior lighting",
    "connectivity & intelligence",
    "connectivity and intelligence",
    "steering wheel & interior rearview mirror",
    "steering wheel and interior rearview mirror",
    "interior charging",
    "seat features",
    "audio & interior lighting",
    "audio and interior lighting",
    "air conditioning & refrigerator",
    "air conditioning and refrigerator",
    "exterior mirrors",
    "whole vehicle",
    "standard/optional",
    "key type",
    "front row",
    "multimedia system",
    "vehicle networking",
    "trip computer display",
    "interior mirror features",
    "number of speakers",
    "number of usb/type-c ports",
    "center console screen size",
    "digital instrument cluster size",
    "driver seat adjustment type",
    "front passenger seat adjustment type",
    "second row seat adjustment",
    "second row seat features",
    "rear seat folding style",
    "ac temperature control method",
    "wheel rim material",
    "low beam light source",
    "high beam light source",
    "power steering type",
    "seat material",
    "steering wheel material",
    "steering wheel adjustment",
    "exterior mirror features",
    "speaker brand name",
    "smartphone connectivity/mirroring",
    "voice recognition control system",
    "color touchscreen display",
    "touchscreen lcd",
    "multimedia/charging ports",
  ].map(normKey),
);

const SINGLE_WORD_NOISE = new Set(
  [
    "sport",
    "economy",
    "standard",
    "comfort",
    "led",
    "laser",
    "usb",
    "type-c",
    "color",
    "colour",
    "speakers",
    "speaker",
    "navigation",
    "telephone",
    "heating",
    "ventilation",
    "multi-color",
    "multicolor",
    "rain-sensing",
    "rain",
    "success",
    "成功",
    "○",
    "aluminum",
    "alloy",
    "genuine",
    "leather",
    "remote",
    "key",
    "standard/optional",
    "front",
    "rear",
    "-",
  ].map(normKey),
);

/** Точные переводы (ключ — normKey). */
const EXACT_RU: Record<string, string> = {
  [normKey("Run-flat Tires")]: "Run-flat шины",
  [normKey("ABS")]: "ABS (антиблокировочная система торможения)",
  [normKey("ESP")]: "ESP (программа стабилизации)",
  [normKey("ESC")]: "ESC (система курсовой устойчивости)",
  [normKey("Brake Force Distribution EBD/CBC")]: "Распределение тормозного усилия (EBD/CBC)",
  [normKey("Brake Assist EBA/BAS/BA")]: "Помощь при экстренном торможении (EBA/BAS/BA)",
  [normKey("Traction Control ASR/TCS/TRC")]: "Противобуксовочная система (ASR/TCS/TRC)",
  [normKey("Tire Pressure Monitoring")]: "Контроль давления в шинах",
  [normKey("Tire pressure display")]: "Индикация давления в шинах",
  [normKey("Seat Belt Reminder")]: "Напоминание о ремне безопасности",
  [normKey("ISOFIX Child Seat Anchors")]: "Крепления ISOFIX для детских кресел",
  [normKey("Autonomous Emergency Braking")]: "Автоматическое экстренное торможение",
  [normKey("Driver Drowsiness Monitoring")]: "Контроль усталости водителя",
  [normKey("Built-in Dash Cam")]: "Встроенный видеорегистратор",
  [normKey("Roadside Assistance Call")]: "Вызов экстренной помощи",
  [normKey("Driving Mode Selection")]: "Выбор режима движения",
  [normKey("Engine Start/Stop System")]: "Система Start/Stop",
  [normKey("Auto Hold")]: "Auto Hold",
  [normKey("Hill Start Assist")]: "Помощь при трогании в гору",
  [normKey("Variable Steering Ratio")]: "Переменное рулевое передаточное число",
  [normKey("Driving Assistance Camera")]: "Камера систем помощи водителю",
  [normKey("Rearview Camera")]: "Камера заднего вида",
  [normKey("360-degree Panoramic View")]: "Камера 360°, панорамный обзор",
  [normKey("Cruise System")]: "Круиз-контроль",
  [normKey("Rear Cross Traffic Alert")]: "Предупреждение о поперечном движении сзади",
  [normKey("Navigation Traffic Display")]: "Навигация с информацией о пробках",
  [normKey("Lane Keeping Assist System")]: "Удержание в полосе",
  [normKey("Road Sign Recognition")]: "Распознавание дорожных знаков",
  [normKey("Power Closing Doors")]: "Доводчики дверей",
  [normKey("Power Tailgate")]: "Электропривод багажника",
  [normKey("Hands-Free Tailgate")]: "Безручное открытие багажника",
  [normKey("Power Tailgate Position Memory")]: "Память положения электропривода багажника",
  [normKey("Roof Rack")]: "Рейлинги на крыше",
  [normKey("Engine Immobilizer")]: "Иммобилайзер",
  [normKey("Central Locking")]: "Центральный замок",
  [normKey("Remote Key")]: "Дистанционный ключ",
  [normKey("Keyless Start System")]: "Бесключевой запуск",
  [normKey("Active Grille Shutters")]: "Активные жалюзи радиатора",
  [normKey("Remote Start Function")]: "Дистанционный запуск",
  [normKey("LED Daytime Running Lights")]: "Светодиодные ДХО",
  [normKey("Adaptive High Beams")]: "Адаптивный дальний свет",
  [normKey("Automatic Headlights")]: "Автоматический включатель фар",
  [normKey("Adaptive Headlights")]: "Адаптивные фары",
  [normKey("Front Fog Lights")]: "Передние противотуманные фары",
  [normKey("Adjustable Headlight Height")]: "Регулировка высоты фар",
  [normKey("Headlight Delay Off")]: "Отложенное выключение фар",
  [normKey("One-touch Power Windows")]: "Стеклоподъёмники one-touch",
  [normKey("Power Window Anti-pinch Function")]: "Антизажим стеклоподъёмников",
  [normKey("Rear Side Window Sunshades")]: "Солнцезащитные шторки задних окон",
  [normKey("Vanity Mirrors")]: "Зеркала в солнцезащитных козырьках",
  [normKey("Driver Side + Illumination")]: "Зеркало водителя с подсветкой",
  [normKey("Passenger Side + Illumination")]: "Зеркало пассажира с подсветкой",
  [normKey("Rear Wiper")]: "Задний стеклоочиститель",
  [normKey("Rain-sensing Wipers")]: "Датчик дождя для дворников",
  [normKey("Power adjustment")]: "Электрорегулировка зеркал",
  [normKey("Power folding")]: "Электроскладывание зеркал",
  [normKey("Mirror memory")]: "Память положения зеркал",
  [normKey("Mirror heating")]: "Обогрев зеркал",
  [normKey("Auto tilt-down in reverse")]: "Наклон зеркала при заднем ходе",
  [normKey("Auto fold when locked")]: "Складывание зеркал при постановке на замок",
  [normKey("Auto-dimming")]: "Автозатемнение зеркал",
  [normKey("12.3 inches")]: "Экран 12,3″",
  [normKey("12.3-inch")]: "Цифровая приборная панель 12,3″",
  [normKey("Bluetooth")]: "Bluetooth",
  [normKey("Supports CarPlay")]: "Apple CarPlay",
  [normKey("Supports CarLife")]: "Baidu CarLife",
  [normKey("Gesture Control")]: "Управление жестами",
  [normKey("OTA Updates")]: "OTA-обновления",
  [normKey("Genuine Leather")]: "Натуральная кожа",
  [normKey("Electric up-down + front-rear adjustment")]: "Электрорегулировка руля (высота и вылет)",
  [normKey("Multi-function Steering Wheel")]: "Многофункциональный руль",
  [normKey("Memory Steering Wheel")]: "Память положения руля",
  [normKey("Full LCD Instrument Cluster")]: "Полностью цифровая приборная панель",
  [normKey("Wireless Phone Charging Function")]: "Беспроводная зарядка телефона",
  [normKey("12V Power Outlet in Trunk")]: "Розетка 12V в багажнике",
  [normKey("Sport Style Seats")]: "Спортивные сиденья",
  [normKey("Backrest adjustment")]: "Регулировка спинки сиденья",
  [normKey("Height adjustment 4-way")]: "4-сторонняя регулировка высоты",
  [normKey("Shoulder adjustment")]: "Регулировка поясничного упора",
  [normKey("Leg rest adjustment")]: "Регулировка подставки для ног",
  [normKey("Lumbar Support 4-way")]: "4-сторонняя поясничная поддержка",
  [normKey("Power-adjustable Driver/Passenger Seats")]: "Электрорегулировка передних сидений",
  [normKey("Power Seat Memory Function")]: "Память положения сидений",
  [normKey("Driver's Seat")]: "Память сиденья водителя",
  [normKey("Rear Adjustable Button for Front Passenger Seat")]: "Регулировка переднего пассажирского сиденья с заднего ряда",
  [normKey("Proportional Folding")]: "Складывание спинки 40/20/40",
  [normKey("Rear Cup Holders")]: "Подстаканники сзади",
  [normKey("Heated/Cooled Cup Holders")]: "Подстаканники с подогревом/охлаждением",
  [normKey("Heating/Cooling")]: "Подогрев и вентиляция",
  [normKey("Harman/Kardon")]: "Аудиосистема Harman/Kardon",
  [normKey("Bowers & Wilkins")]: "Аудиосистема Bowers & Wilkins",
  [normKey("Ambient Interior Lighting")]: "Ambient-подсветка салона",
  [normKey("Automatic Air Conditioning")]: "Автоматический климат-контроль",
  [normKey("Rear Air Vents")]: "Дефлекторы обдува для заднего ряда",
  [normKey("In-vehicle Air Purifier")]: "Очиститель воздуха в салоне",
  [normKey("PM2.5 Air Filter")]: "Фильтр PM2.5",
  [normKey("Negative Ion Generator")]: "Генератор отрицательных ионов",
  [normKey("In-Car Fragrance System")]: "Система ароматизации салона",
  [normKey("Adaptive cruise control")]: "Адаптивный круиз-контроль",
  [normKey("Panoramic sunroof")]: "Панорамная крыша",
  [normKey("Head-up display")]: "Проекционный дисплей",
  [normKey("Blind spot monitoring")]: "Контроль слепых зон",
};

/** Правила по полной строке (длинные — раньше). */
const LINE_RULES: [RegExp, string][] = [
  [/^adaptive cruise control$/i, "Адаптивный круиз-контроль"],
  [/^lane keeping assist system$/i, "Удержание в полосе"],
  [/^lane departure warning$/i, "Предупреждение о смене полосы"],
  [/^blind spot (?:monitoring|detection|assist)$/i, "Контроль слепых зон"],
  [/^surround view camera$/i, "Камера 360°"],
  [/^panoramic sunroof$/i, "Панорамная крыша"],
  [/^heated steering wheel$/i, "Подогрев руля"],
  [/^wireless (?:phone )?charg/i, "Беспроводная зарядка"],
  [/^keyless entry$/i, "Бесключевой доступ"],
  [/^apple carplay$/i, "Apple CarPlay"],
  [/^android auto$/i, "Android Auto"],
  [/^parking assist/i, "Парковочный ассистент"],
  [/^power tailgate position memory$/i, "Память положения электропривода багажника"],
  [/^power tailgate$/i, "Электропривод багажника"],
  [/^electric tailgate$/i, "Электропривод багажника"],
  [/^memory seat$/i, "Память сидений"],
  [/^massage seat/i, "Массаж сидений"],
  [/^heated seat/i, "Подогрев сидений"],
  [/^ventilated seat/i, "Вентиляция сидений"],
  [/^climate control$/i, "Климат-контроль"],
  [/^navigation system$/i, "Навигация"],
  [/^cruise control$/i, "Круиз-контроль"],
  [/^sunroof$/i, "Люк"],
  [/^run-?flat tire/i, "Run-flat шины"],
  [/^tire pressure/i, "Контроль давления в шинах"],
  [/^front fog lights$/i, "Передние противотуманные фары"],
  [/^rain.?sensing wiper/i, "Датчик дождя для дворников"],
  [/^road sign recognition$/i, "Распознавание дорожных знаков"],
  [/^rear cross traffic alert$/i, "Предупреждение о поперечном движении сзади"],
  [/^autonomous emergency braking$/i, "Автоматическое экстренное торможение"],
  [/^driver drowsiness monitoring$/i, "Контроль усталости водителя"],
  [/^built-?in dash cam$/i, "Встроенный видеорегистратор"],
  [/^engine start\/stop system$/i, "Система Start/Stop"],
  [/^hill start assist$/i, "Помощь при трогании в гору"],
  [/^variable steering ratio$/i, "Переменное рулевое передаточное число"],
  [/^rearview camera$/i, "Камера заднего вида"],
  [/^360.?degree panoramic view$/i, "Камера 360°, панорамный обзор"],
  [/^brake force distribution/i, "Распределение тормозного усилия (EBD/CBC)"],
  [/^brake assist/i, "Помощь при экстренном торможении (EBA/BAS/BA)"],
  [/^traction control/i, "Противобуксовочная система (ASR/TCS/TRC)"],
  [/^isofix child seat anchors$/i, "Крепления ISOFIX для детских кресел"],
  [/^seat belt reminder$/i, "Напоминание о ремне безопасности"],
  [/^central locking$/i, "Центральный замок"],
  [/^engine immobilizer$/i, "Иммобилайзер"],
  [/^supports carplay$/i, "Apple CarPlay"],
  [/^supports carlife$/i, "Baidu CarLife"],
  [/^ota updates$/i, "OTA-обновления"],
  [/^ambient interior lighting$/i, "Ambient-подсветка салона"],
  [/^automatic air conditioning$/i, "Автоматический климат-контроль"],
  [/^in-vehicle air purifier$/i, "Очиститель воздуха в салоне"],
  [/^in-car fragrance system$/i, "Система ароматизации салона"],
  [/^harman\/?kardon$/i, "Аудиосистема Harman/Kardon"],
  [/^bowers & wilkins$/i, "Аудиосистема Bowers & Wilkins"],
  [/^sport style seats$/i, "Спортивные сиденья"],
  [/^power.?adjustable driver\/passenger seats$/i, "Электрорегулировка передних сидений"],
  [/^power seat memory function$/i, "Память положения сидений"],
  [/^full lcd instrument cluster$/i, "Полностью цифровая приборная панель"],
  [/^wireless phone charging function$/i, "Беспроводная зарядка телефона"],
  [/^multi-?function steering wheel$/i, "Многофункциональный руль"],
  [/^memory steering wheel$/i, "Память положения руля"],
  [/^genuine leather$/i, "Натуральная кожа"],
  [/^aluminum alloy$/i, "Литые диски (алюминиевый сплав)"],
  [/^standard\/comfort$/i, "Режим Standard/Comfort"],
  [/^front row:\s*\d+$/i, ""],
  [/^\d+(\.\d+)?\s*(-?\s*)?(inch|inches|″)$/i, ""],
];

function isFieldLabelNoise(src: string): boolean {
  const low = src.toLowerCase().trim();
  if (CATEGORY_HEADERS.has(normKey(low))) return true;
  if (SINGLE_WORD_NOISE.has(normKey(low))) return true;
  if (/^(?:driving|exterior|interior|seat|audio|air conditioning|steering wheel|connectivity)\b/i.test(low))
    return true;
  if (/\b(material|adjustment type|folding style|brand name|control system|screen size|cluster size|charging ports|mirror features|seat features|light source|rim material|temperature control method|networking|function|ports|selection|hardware)\s*$/i.test(low))
    return true;
  if (/^number of /i.test(low)) return true;
  if (/^front row\b/i.test(low)) return true;
  if (/^standard\/optional$/i.test(low)) return true;
  return false;
}

export function isChinaOptionNoise(label: string): boolean {
  const t = label.trim();
  if (!t) return true;
  if (/^\d+$/.test(t)) return true;
  if (/^[\W_]+$/.test(t)) return true;
  if (/^[○◆▪\-–—]+$/.test(t)) return true;
  if (/[●◆▪]/.test(t)) return true;
  if (/^成功$/.test(t)) return true;
  if (/^\s*(?:front|rear|primary|secondary|color)\b/i.test(t)) return true;
  if (/\b\d+\s+colors?\s*$/i.test(t)) return true;
  if (/primary\s*●|secondary\s*●|front\s*●\s*\/\s*rear/i.test(t)) return true;
  if (/^front\s*\/\s*rear\s*-?\s*$/i.test(t)) return true;
  if (isFieldLabelNoise(t)) return true;
  return false;
}

export function displayChinaOptionRu(raw: string): string {
  const src = raw.trim();
  if (!src) return "";
  if (/^[\W_]+$/.test(src) || /^成功$/.test(src) || /^[○◆▪\-–—]+$/.test(src)) return "";

  const cyrCount = (src.match(CYRILLIC_RE) ?? []).length;
  if (cyrCount > 0 && cyrCount / src.length > 0.35) return src;

  const exact = EXACT_RU[normKey(src)];
  if (exact) return exact;

  for (const [rx, repl] of LINE_RULES) {
    if (rx.test(src)) {
      const out = repl.trim();
      return out || "";
    }
  }

  if (/^abs$/i.test(src)) return "ABS (антиблокировочная система торможения)";
  if (/^esp$/i.test(src)) return "ESP (программа стабилизации)";
  if (/^esc$/i.test(src)) return "ESC (система курсовой устойчивости)";

  if (isChinaOptionNoise(src)) return "";

  if (!CYRILLIC_RE.test(src) && /^[a-z0-9\s/\-().&+,]+$/i.test(src)) return "";

  return src;
}

const GROUP_KEYWORDS: Record<ChinaOptionGroup, string[]> = {
  assist: [
    "круиз",
    "ассист",
    "удерж",
    "полос",
    "автопарков",
    "парков",
    "слеп",
    "lane",
    "blind",
    "камера",
    "360",
    "панорам",
    "знак",
    "движен",
    "cross traffic",
    "emergency braking",
    "drowsiness",
    "dash cam",
    "roadside",
    "cruise",
    "rearview",
    "panoramic view",
    "keeping",
    "sign recognition",
    "попереч",
  ],
  interior: [
    "интерьер",
    "экстерь",
    "салон",
    "сиден",
    "руль",
    "люк",
    "панорам",
    "зеркал",
    "диск",
    "кож",
    "leather",
    "sunroof",
    "roof rack",
    "tailgate",
    "багажник",
    "двер",
    "окн",
    "wiper",
    "дворник",
    "fog light",
    "headlight",
    "beam",
    "grille",
    "immobilizer",
    "locking",
    "keyless",
    "wheel rim",
    "alloy",
    "cup holder",
    "folding",
    "ambient",
    "подсвет",
    "instrument cluster",
    "steering",
    "seat",
    "mirror",
    "vanity",
  ],
  safety: [
    "airbag",
    "подуш",
    "abs",
    "esp",
    "esc",
    "тормоз",
    "безопас",
    "столкнов",
    "isofix",
    "belt",
    "ремн",
    "brake",
    "traction",
    "run-flat",
    "tire pressure",
    "давлен",
    "шин",
    "ebd",
    "bas",
    "asr",
  ],
  comfort: [
    "подогрев",
    "вентиляц",
    "климат",
    "кондиц",
    "электропривод",
    "память",
    "memory",
    "massage",
    "massage",
    "lumbar",
    "leg rest",
    "shoulder",
    "height adjustment",
    "wireless charg",
    "start/stop",
    "auto hold",
    "hill start",
    "air purifier",
    "pm2.5",
    "fragrance",
    "ion generator",
    "air vent",
    "power-adjustable",
    "power seat",
    "heated",
    "ventilation",
    "cooling",
    "climate",
    "air conditioning",
    "charging function",
    "12v power",
  ],
  media: [
    "мультимед",
    "навигац",
    "carplay",
    "carlife",
    "android auto",
    "bluetooth",
    "аудио",
    "дисплей",
    "hud",
    "harman",
    "bowers",
    "speaker",
    "gesture",
    "ota",
    "navigation",
    "traffic display",
    "touchscreen",
    "lcd",
    "usb",
    "type-c",
    "telephone",
    "multimedia",
    "экран",
    "проекцион",
  ],
  other: [],
};

/** Группа опции для вкладок «Комплектация». */
export function classifyChinaOptionGroup(label: string, rawEn = ""): ChinaOptionGroup {
  const hay = `${label} ${rawEn}`.toLowerCase();
  const order: ChinaOptionGroup[] = ["assist", "safety", "media", "comfort", "interior"];
  for (const key of order) {
    if (GROUP_KEYWORDS[key].some((kw) => hay.includes(kw))) return key;
  }
  return "other";
}
