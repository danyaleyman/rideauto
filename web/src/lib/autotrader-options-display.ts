/** EN → RU для комплектации Autotrader (features / ranked_features). */

const CYRILLIC_RE = /[\u0400-\u04FF]/;

function normKey(s: string): string {
  return s
    .trim()
    .toLowerCase()
    .replace(/&/g, "and")
    .replace(/[\s\-_:/()（）[\]【】.+,®™']+/g, "");
}

/** Шум: цвета, пакеты опций, служебные строки. */
export function isAutotraderOptionNoise(raw: string): boolean {
  const t = raw.trim();
  if (!t) return true;
  const k = normKey(t);
  if (!k) return true;
  if (/^optiongroup\d/.test(k)) return true;
  if (/^requires?subscription$/.test(k)) return true;
  if (/^incstandardequipment/.test(k)) return true;
  // Pure color / paint names without equipment keywords
  if (/^(shimmeringsilver|silver|black|white|gray|grey|red|blue|green|beige|brown|orange|yellow|gold|pearl|metallic)$/.test(k)) {
    return true;
  }
  if (/^[a-z]+quiltedpremiumnappaleatherseattrim$/.test(k)) return false;
  return false;
}

const EXACT_RU: Record<string, string> = {
  // Safety / brakes
  abs: "ABS",
  absbrakes: "ABS",
  "4wheeldiscbrakes": "Дисковые тормоза на 4 колеса",
  brakeassist: "Помощь при экстренном торможении",
  electronicstabilitycontrol: "Электронная система стабилизации",
  tractioncontrol: "Система контроля тяги",
  lowtirepressurewarning: "Датчик давления в шинах",
  dualfrontimpactairbags: "Фронтальные подушки безопасности",
  dualfrontsideimpactairbags: "Боковые подушки безопасности спереди",
  rearsideimpactairbag: "Боковая подушка безопасности сзади",
  overheadairbag: "Подушка безопасности в потолке",
  kneeairbag: "Подушка безопасности для коленей",
  occupantsensingairbag: "Датчик присутствия пассажира (подушка)",
  panicalarm: "Тревожная кнопка",
  securitysystem: "Сигнализация",
  firstaidkit: "Аптечка",
  roadsideassistancekit: "Набор помощи на дороге",

  // Drive / chassis
  allwheeldrive: "Полный привод",
  turbocharged: "Турбонаддув",
  fourwheelindependentsuspension: "Независимая подвеска на 4 колеса",
  frontantirollback: "Стабилизатор поперечной устойчивости спереди",
  rearantirollback: "Стабилизатор поперечной устойчивости сзади",
  speedsensingsteering: "Адаптивное рулевое управление",
  powerssteering: "Усилитель руля",
  powersteering: "Усилитель руля",
  lithiumiontractionbattery: "Тяговая батарея Li-Ion",

  // Exterior / lights / mirrors
  alloywheels: "Легкосплавные диски",
  aluminumwheels: "Алюминиевые диски",
  autohighbeamheadlights: "Автоматический дальний свет",
  automaticheadlights: "Автоматические фары",
  automatichighbeams: "Автоматический дальний свет",
  daytimeunninglights: "Дневные ходовые огни",
  daytimerunninglights: "Дневные ходовые огни",
  delayoffheadlights: "Задержка выключения фар",
  fullyautomaticheadlights: "Полностью автоматические фары",
  ledheadlights: "Светодиодные фары",
  heatedmirrors: "Подогрев зеркал",
  heateddoormirrors: "Подогрев зеркал",
  integratedturnsignalmirrors: "Повторители поворотов в зеркалах",
  turnsignalindicatormirrors: "Повторители поворотов в зеркалах",
  mirrormemory: "Память настроек зеркал",
  powerfoldingmirrors: "Складываемые электрозеркала",
  powermirrors: "Электрозеркала",
  powerdoormirrors: "Электрозеркала",
  rearspoiler: "Задний спойлер",
  spoiler: "Спойлер",
  rearwindowwiper: "Задний дворник",
  tiresfrontperformance: "Шины Performance (перед)",
  tiresrearperformance: "Шины Performance (зад)",
  bumpersbodycolor: "Бамперы в цвет кузова",
  privacyglass: "Тонированные стёкла",
  handsfredliftgate: "Бесконтактная задняя дверь",
  "hands-freeliftgate": "Бесконтактная задняя дверь",
  handsfreedliftgate: "Бесконтактная задняя дверь",
  "handsfreeliftgate": "Бесконтактная задняя дверь",
  powerliftgate: "Электропривод задней двери",
  genericssunmoonroof: "Люк",
  genericsunmoonroof: "Люк",
  sunmoonroof: "Люк",
  dualmoonroof: "Двойной люк",
  powermoonroof: "Электролюк",
  rainsensingwipers: "Дворники с датчиком дождя",
  intermittentrwipers: "Прерывистые дворники",
  intermittentwipers: "Прерывистые дворники",
  variablespeedintermittentwipers: "Дворники с регулируемой паузой",
  variablyintermittentwipers: "Дворники с регулируемой паузой",
  reardefrost: "Обогрев заднего стекла",
  rearwindowdefroster: "Обогрев заднего стекла",

  // Interior / seats / climate
  "3rdrowseat": "Третий ряд сидений",
  "3rdrowseatsbench": "Третий ряд: диван",
  ac: "Кондиционер",
  airconditioning: "Кондиционер",
  climatecontrol: "Климат-контроль",
  automatictemperaturecontrol: "Автоматический климат-контроль",
  frontdualzoneac: "Двухзонный климат спереди",
  multizoneac: "Многозонный климат-контроль",
  adjustablesteeringwheel: "Регулируемый руль",
  telescopingsteeringwheel: "Телескопический руль",
  tiltsteeringwheel: "Руль с наклоном",
  heatedsteeringwheel: "Подогрев руля",
  leathersteeringwheel: "Кожаный руль",
  autodimmingrearviewmirror: "Салонное зеркало с автозатемнением",
  bucketseats: "Спортивные сиденья",
  frontbucketseats: "Передние спортивные сиденья",
  rearbucketseats: "Задние раздельные сиденья",
  cooledfrontseats: "Вентиляция передних сидений",
  heatedfrontseats: "Подогрев передних сидений",
  heatedrearseats: "Подогрев задних сидений",
  ventilatedfrontseats: "Вентиляция передних сидений",
  heatedandventilatedfrontbucketseats: "Подогрев и вентиляция передних сидений",
  leatherseats: "Кожаный салон",
  quiltedpremiumnappaleatherseattrim: "Отделка сидений кожей Nappa",
  driveradjustablelumbar: "Поясничная поддержка водителя",
  powerdriverseat: "Электропривод сиденья водителя",
  powerpassengerseat: "Электропривод сиденья пассажира",
  seatmemory: "Память настроек сидений",
  memoryseat: "Память сиденья",
  splitfoldingrearseat: "Складываемый задний ряд",
  frontcenterarmrest: "Передний центральный подлокотник",
  cargocovercreen: "Шторка багажника",
  cargocoverscreen: "Шторка багажника",
  cargonet: "Сетка в багажник",
  cargoorganizer: "Органайзер багажника",
  cargotray: "Коврик багажника",
  carpetedfloormats: "Ковровые коврики",
  woodgraininteriortrim: "Отделка салона под дерево",
  illuminatedentry: "Подсветка при посадке",
  frontreadinglights: "Передние лампы для чтения",
  outsidetemperaturedisplay: "Датчик наружной температуры",
  tachometer: "Тахометр",
  tripcomputer: "Бортовой компьютер",
  headsupdisplay: "Проекционный дисплей",
  overheadconsole: "Потолочная консоль",
  driverdoorbin: "Карман в двери водителя",
  passengerdoorbin: "Карман в двери пассажира",
  drivervanitymirror: "Зеркало в козырьке водителя",
  passengervanitymirror: "Зеркало в козырьке пассажира",
  driverilluminatedvanitymirror: "Подсветка зеркала водителя",
  passengerilluminatedvisormirror: "Подсветка зеркала пассажира",
  adjustableheadrestraintsdriverandpassengerwtilt: "Регулируемые подголовники",

  // Comfort / access
  cruisecontrol: "Круиз-контроль",
  adaptivecruisecontrol: "Адаптивный круиз-контроль",
  speedcontrol: "Круиз-контроль",
  keylessentry: "Бесключевой доступ",
  remotekeylessentry: "Дистанционный бесключевой доступ",
  keylessstart: "Бесключевой запуск",
  remotenginestart: "Дистанционный запуск двигателя",
  remoteenginestart: "Дистанционный запуск двигателя",
  remotetrunkrelease: "Дистанционное открытие багажника",
  powerdoorlocks: "Центральный замок с электроприводом",
  powerwindows: "Электростеклоподъёмники",
  universalgaragedooropener: "Универсальный пульт гаража",
  garagedoortransmitterhomelink: "HomeLink (гараж)",

  // Media / connectivity
  amfmstereo: "AM/FM радио",
  amfmradiosiriusxm: "Радио AM/FM + SiriusXM",
  satelliteradio: "Спутниковое радио",
  hdradio: "HD Radio",
  premiumsoundsystem: "Премиальная аудиосистема",
  radioamfmhdbosepremiumaudiosystem: "Аудиосистема Bose Premium",
  "12speakers": "12 динамиков",
  auxiliaryaudioinput: "AUX-вход",
  mp3capability: "Поддержка MP3",
  bluetoothconnection: "Bluetooth",
  applecarplayandandroidauto: "Apple CarPlay и Android Auto",
  smartdeviceintegration: "Интеграция смартфона",
  navigationsystem: "Навигация",
  wifihotspot: "Wi‑Fi точка доступа",
  steeringwheelaudiocontrols: "Управление аудио на руле",
  steeringwheelmountedaudiocontrols: "Управление аудио на руле",
  emergencycommunicationsystem: "Система экстренной связи",

  // Camera / park
  exteriorparkingcamerarear: "Камера заднего вида",
};

/** Нормализованный ключ → русский ярлык (пополнять по живым VDP). */
const RU_BY_NORM: Record<string, string> = (() => {
  const out: Record<string, string> = {};
  for (const [k, v] of Object.entries(EXACT_RU)) {
    out[normKey(k)] = v;
  }
  // Extra aliases / casing variants from Autotrader dumps
  const aliases: Array<[string, string]> = [
    ["Hands-Free Liftgate", "Бесконтактная задняя дверь"],
    ["A/C", "Кондиционер"],
    ["ABS brakes", "ABS"],
    ["Brake assist", "Помощь при экстренном торможении"],
    ["Auto-dimming Rear-View mirror", "Салонное зеркало с автозатемнением"],
    ["Auto-Dimming Rearview Mirror", "Салонное зеркало с автозатемнением"],
    ["Heated front seats", "Подогрев передних сидений"],
    ["Heated rear seats", "Подогрев задних сидений"],
    ["Heated steering wheel", "Подогрев руля"],
    ["Leather steering wheel", "Кожаный руль"],
    ["Power driver seat", "Электропривод сиденья водителя"],
    ["Power passenger seat", "Электропривод сиденья пассажира"],
    ["Power door mirrors", "Электрозеркала"],
    ["Power Mirror(s)", "Электрозеркала"],
    ["Power windows", "Электростеклоподъёмники"],
    ["Power steering", "Усилитель руля"],
    ["Rain sensing wipers", "Дворники с датчиком дождя"],
    ["Remote keyless entry", "Дистанционный бесключевой доступ"],
    ["Trip computer", "Бортовой компьютер"],
    ["Heads-Up Display", "Проекционный дисплей"],
    ["Heads-Up Display>", "Проекционный дисплей"],
    ["Cooled Front Seat(s)", "Вентиляция передних сидений"],
    ["Heated Front Seat(s)", "Подогрев передних сидений"],
    ["Heated Rear Seat(s)", "Подогрев задних сидений"],
    ["Apple CarPlay & Android Auto", "Apple CarPlay и Android Auto"],
    ["WiFi Hotspot", "Wi‑Fi точка доступа"],
    ["Cargo Cover/Screen", "Шторка багажника"],
    ["CARGO COVER/SCREEN", "Шторка багажника"],
    ["Front anti-roll bar", "Стабилизатор поперечной устойчивости спереди"],
    ["Rear anti-roll bar", "Стабилизатор поперечной устойчивости сзади"],
    ["Multi-Zone A/C", "Многозонный климат-контроль"],
    ["Front dual zone A/C", "Двухзонный климат спереди"],
  ];
  for (const [en, ru] of aliases) {
    out[normKey(en)] = ru;
  }
  return out;
})();

export function displayAutotraderOptionRu(raw: string): string {
  const t = raw.trim();
  if (!t) return "";
  if (CYRILLIC_RE.test(t)) return t;
  if (isAutotraderOptionNoise(t)) return "";
  const mapped = RU_BY_NORM[normKey(t)];
  if (mapped) return mapped;
  // Soft cleanup for unmapped English: keep readable, do not invent translation.
  return t.replace(/\s*>\s*$/, "").replace(/\s+/g, " ").trim();
}

export type AutotraderOptionGroup = "assist" | "interior" | "safety" | "comfort" | "media" | "other";

const GROUP_HINTS: Array<{ group: AutotraderOptionGroup; re: RegExp }> = [
  {
    group: "safety",
    re: /airbag|abs|brake|stability|traction|tire pressure|alarm|security|first aid|roadside|подушк|тормоз|стабилиз|тяг|давлен|сигнал|аптечк/i,
  },
  {
    group: "assist",
    re: /cruise|camera|parking|lane|blind|assist|heads-?up|navigation|adaptive|круиз|камер|парков|навигац|проекцион/i,
  },
  {
    group: "media",
    re: /radio|audio|speaker|bluetooth|carplay|android|wifi|hd radio|satellite|mp3|aux|bose|sirius|радио|аудио|динамик|wi‑?fi|bluetooth/i,
  },
  {
    group: "comfort",
    re: /climate|a\/c|air conditioning|heated|ventilated|cooled|keyless|remote|moonroof|sunroof|liftgate|wiper|home.?link|garage|климат|кондицион|подогрев|вентиляц|бесключ|дистанц|люк|дворник|гараж/i,
  },
  {
    group: "interior",
    re: /seat|leather|steering|mirror|console|cargo|floor mat|woodgrain|armrest|vanity|reading light|tachometer|trip computer|сиден|кож|рул|зеркал|консол|багаж|коврик|подлокот|тахометр|компьютер/i,
  },
];

export function classifyAutotraderOptionGroup(label: string, raw = label): AutotraderOptionGroup {
  const sample = `${label} ${raw}`;
  for (const { group, re } of GROUP_HINTS) {
    if (re.test(sample)) return group;
  }
  return "other";
}
