import {
  asStr,
  formatInspectionListItem,
  getPath,
  translateKoToRuText,
} from "@/lib/car-detail-data";

export type BodyPanelRow = { part: string; status: string; section?: "external" | "internal" };

export type BodyPanelGroups = { external: BodyPanelRow[]; internal: BodyPanelRow[] };

export function normalizeBodyStatus(raw: string): string {
  const t = raw.toLowerCase();
  if (t.includes("교환") || t.includes("замен")) return "Замена";
  if (t.includes("용접") || t.includes("свар")) return "Сварка";
  if (t.includes("도장") || t.includes("окрас")) return "Окрас";
  if (t.includes("판금") || t.includes("ремонт")) return "Ремонт";
  if (t.includes("부식") || t.includes("корроз")) return "Коррозия";
  if (t.includes("흠집") || t.includes("царап")) return "Царапина";
  if (t.includes("요철") || t.includes("вмят")) return "Вмятина";
  if (t.includes("손상") || t.includes("повреж")) return "Повреждение";
  if (t.includes("정상") || t.includes("양호") || t.includes("normal") || t.includes("없음") || t.includes("ориг")) {
    return "Оригинал";
  }
  return translateKoToRuText(raw) || "Оригинал";
}

export function bodyStatusColor(text: string): string {
  const t = normalizeBodyStatus(text).toLowerCase();
  if (t.includes("ориг")) return "bg-emerald-100 text-emerald-900 border-emerald-300";
  if (t.includes("окрас") || t.includes("ремонт") || t.includes("царап")) return "bg-amber-100 text-amber-900 border-amber-300";
  if (t.includes("свар") || t.includes("замен") || t.includes("дтп")) return "bg-red-100 text-red-900 border-red-300";
  if (t.includes("вмят") || t.includes("повреж") || t.includes("корроз")) return "bg-orange-100 text-orange-900 border-orange-300";
  return "bg-slate-100 text-slate-800 border-slate-300";
}

function bodyStatusWeight(status: string): number {
  const s = normalizeBodyStatus(status).toLowerCase();
  if (s.includes("замен")) return 50;
  if (s.includes("свар")) return 40;
  if (s.includes("повреж") || s.includes("вмят")) return 30;
  if (s.includes("окрас") || s.includes("ремонт") || s.includes("корроз")) return 20;
  if (s.includes("царап")) return 10;
  return 0;
}

function isInternalBodyPart(part: string): boolean {
  const p = part.toLowerCase();
  const keys = [
    "pillar", "frame", "floor", "wheel housing", "member", "package tray", "대시", "필러", "플로어",
    "휠하우스", "사이드실", "주요골격", "트렁크 플로어", "루프", "лонжерон", "стойк", "порог",
    "서포트", "support", "radiator", "радиатор", "패널 / 인사이드", "inside panel", "side member",
    "package tray", "cross member", "dash panel", "wheelhouse", "sill panel",
  ];
  const externalOnly = ["крыл", "fender", "휀더", "펜더", "двер", "door", "капот", "hood", "багажник", "trunk"];
  if (externalOnly.some((k) => p.includes(k))) return false;
  return keys.some((k) => p.includes(k));
}

function normalizeBodyPartName(partRaw: string): string {
  const p = partRaw.trim();
  const map: Record<string, string> = {
    "프론트 도어(좌)": "Левая передняя дверь",
    "프론트 도어(우)": "Правая передняя дверь",
    "리어 도어(좌)": "Левая задняя дверь",
    "리어 도어(우)": "Правая задняя дверь",
    "프론트 펜더(좌)": "Левое переднее крыло",
    "프론트 펜더(우)": "Правое переднее крыло",
    "프론트 휀더(좌)": "Левое переднее крыло",
    "프론트 휀더(우)": "Правое переднее крыло",
    "리어 휀더(좌)": "Левое заднее крыло",
    "리어 휀더(우)": "Правое заднее крыло",
    "라디에이터 서포트(볼트체결부품)": "Крепление радиатора",
    "라디에이터 서포트": "Крепление радиатора",
    "리어 펜더(좌)": "Левое заднее крыло",
    "리어 펜더(우)": "Правое заднее крыло",
    "쿼터 패널(좌)": "Левое заднее крыло",
    "쿼터 패널(우)": "Правое заднее крыло",
    "트렁크 리드": "Крышка багажника",
    "후드": "Капот",
    "프론트 패널 / 인사이드 패널": "Передняя панель / внутренняя панель",
    "앞휠하우스 / 뒷휠하우스": "Арки колес (перед/зад)",
    "필러패널(A/B) / 대쉬패널 / 플로어패널": "Стойки / щиток / пол",
    "사이드실 패널 / 쿼터패널": "Пороги / четверти кузова",
    "리어패널 / 트렁크 플로어": "Задняя панель / пол багажника",
    "사이드멤버 / 루프패널 / 패키지트레이": "Лонжероны / крыша / полка багажника",
  };
  return map[p] ?? translateKoToRuText(p);
}

function withOriginalDefaults(rows: BodyPanelRow[], section: "external" | "internal"): BodyPanelRow[] {
  const defaults =
    section === "external"
      ? [
          "Левое переднее крыло",
          "Правое переднее крыло",
          "Левая передняя дверь",
          "Правая передняя дверь",
          "Левая задняя дверь",
          "Правая задняя дверь",
          "Левое заднее крыло",
          "Правое заднее крыло",
          "Капот",
          "Крышка багажника",
        ]
      : [
          "Передняя панель / внутренняя панель",
          "Арки колес (перед/зад)",
          "Стойки / щиток / пол",
          "Пороги / четверти кузова",
          "Задняя панель / пол багажника",
          "Лонжероны / полка багажника",
        ];
  if (!rows.length) {
    return defaults.map((part) => ({ part, status: "Оригинал", section }));
  }
  const seen = new Set(rows.map((r) => r.part.trim().toLowerCase()));
  const out = [...rows];
  for (const part of defaults) {
    if (!seen.has(part.trim().toLowerCase())) out.push({ part, status: "Оригинал", section });
  }
  return out;
}

export function hasStructuredBodyPayload(
  bodyPanels: unknown,
  outers: unknown,
  bodyChanged: unknown,
  paintPartTypes: unknown,
  seriousTypes: unknown,
  diagnosisItems: unknown,
): boolean {
  if (Array.isArray(bodyPanels) && bodyPanels.length > 0) return true;
  if (Array.isArray(outers) && outers.length > 0) return true;
  if (bodyChanged && typeof bodyChanged === "object" && !Array.isArray(bodyChanged)) {
    if (Object.keys(bodyChanged as Record<string, unknown>).length > 0) return true;
  }
  if (Array.isArray(paintPartTypes) && paintPartTypes.length > 0) return true;
  if (Array.isArray(seriousTypes) && seriousTypes.length > 0) return true;
  if (Array.isArray(diagnosisItems) && diagnosisItems.length > 0) return true;
  return false;
}

export function collectBodyRows({
  outers,
  bodyPanels,
  bodyChanged,
  paintPartTypes,
  seriousTypes,
  diagnosisItems,
}: {
  outers: unknown;
  bodyPanels: unknown;
  bodyChanged: unknown;
  paintPartTypes: unknown;
  seriousTypes: unknown;
  diagnosisItems: unknown;
}): BodyPanelGroups {
  const rows: BodyPanelRow[] = [];
  if (Array.isArray(bodyPanels)) {
    for (const panel of bodyPanels) {
      if (!panel || typeof panel !== "object") continue;
      const p = panel as Record<string, unknown>;
      const part = translateKoToRuText(asStr(p.part) ?? asStr(p.name) ?? "");
      const status = normalizeBodyStatus(asStr(p.status) ?? "Оригинал");
      const sectionRaw = asStr(p.section)?.toLowerCase();
      const section = sectionRaw === "internal" || sectionRaw === "external" ? sectionRaw : undefined;
      if (part && status) rows.push({ part, status, section });
    }
  }
  if (Array.isArray(outers)) {
    for (const item of outers) {
      if (!item || typeof item !== "object") continue;
      const o = item as Record<string, unknown>;
      const partRaw =
        asStr(o.partName) ??
        asStr(o.part) ??
        asStr(o.name) ??
        asStr(o.title) ??
        asStr(getPath(o, ["type", "title"])) ??
        "";
      const statusTypes = getPath(o, ["statusTypes"]);
      const firstStatus =
        Array.isArray(statusTypes) && statusTypes[0] && typeof statusTypes[0] === "object"
          ? asStr(getPath(statusTypes[0], ["title"]))
          : null;
      const part = normalizeBodyPartName(partRaw);
      const status = normalizeBodyStatus(
        asStr(getPath(o, ["statusType", "title"])) ??
          firstStatus ??
          asStr(o.status) ??
          asStr(o.result) ??
          "Оригинал",
      );
      if (part && status) {
        rows.push({ part, status, section: isInternalBodyPart(part) ? "internal" : "external" });
      }
    }
  }
  if (bodyChanged && typeof bodyChanged === "object" && !Array.isArray(bodyChanged)) {
    for (const [k, v] of Object.entries(bodyChanged as Record<string, unknown>)) {
      const part = translateKoToRuText(k);
      const status = normalizeBodyStatus(asStr(v) ?? "Замена");
      if (part && status) {
        rows.push({ part, status, section: isInternalBodyPart(part) ? "internal" : "external" });
      }
    }
  }
  if (Array.isArray(paintPartTypes)) {
    for (const x of paintPartTypes) {
      const part = translateKoToRuText(typeof x === "object" ? formatInspectionListItem(x) : String(x));
      if (part) rows.push({ part, status: "Окрас", section: isInternalBodyPart(part) ? "internal" : "external" });
    }
  }
  if (Array.isArray(seriousTypes)) {
    for (const x of seriousTypes) {
      const part = translateKoToRuText(typeof x === "object" ? formatInspectionListItem(x) : String(x));
      if (part) rows.push({ part, status: "Повреждение", section: isInternalBodyPart(part) ? "internal" : "external" });
    }
  }
  if (Array.isArray(diagnosisItems)) {
    const nameMap: Record<string, { part: string; section: "external" | "internal" }> = {
      FRONT_DOOR_LEFT: { part: "Левая передняя дверь", section: "external" },
      FRONT_DOOR_RIGHT: { part: "Правая передняя дверь", section: "external" },
      BACK_DOOR_LEFT: { part: "Левая задняя дверь", section: "external" },
      BACK_DOOR_RIGHT: { part: "Правая задняя дверь", section: "external" },
      HOOD: { part: "Капот", section: "external" },
      TRUNK_LID: { part: "Крышка багажника", section: "external" },
      FRONT_FENDER_LEFT: { part: "Левое переднее крыло", section: "external" },
      FRONT_FENDER_RIGHT: { part: "Правое переднее крыло", section: "external" },
      REAR_FENDER_LEFT: { part: "Левое заднее крыло", section: "external" },
      REAR_FENDER_RIGHT: { part: "Правое заднее крыло", section: "external" },
      BACK_FENDER_LEFT: { part: "Левое заднее крыло", section: "external" },
      BACK_FENDER_RIGHT: { part: "Правое заднее крыло", section: "external" },
      FRONT_FENDER: { part: "Передние крылья", section: "external" },
      FRONT_DOOR: { part: "Передние двери", section: "external" },
      BACK_DOOR: { part: "Задние двери", section: "external" },
      FRONT_PANEL_INSIDE_PANEL: { part: "Передняя панель / внутренняя панель", section: "internal" },
      FRONT_WHEEL_HOUSING_REAR_WHEEL_HOUSING: { part: "Арки колес (перед/зад)", section: "internal" },
      PILLAR_PANEL_DASH_PANEL_FLOOR_PANEL: { part: "Стойки / щиток / пол", section: "internal" },
      SIDE_SILL_PANEL_QUARTER_PANEL: { part: "Пороги / четверти кузова", section: "internal" },
      REAR_PANEL_TRUNK_FLOOR: { part: "Задняя панель / пол багажника", section: "internal" },
      SIDE_MEMBER_LOOP_PANEL_PACKAGE_TRAY: { part: "Лонжероны / полка багажника", section: "internal" },
    };
    const codeMap: Record<string, string> = {
      NORMAL: "Оригинал",
      REPLACEMENT: "Замена",
      PAINT: "Окрас",
      REPAIR: "Ремонт",
    };
    for (const item of diagnosisItems) {
      if (!item || typeof item !== "object") continue;
      const it = item as Record<string, unknown>;
      const name = asStr(it.name) ?? "";
      const mapped = nameMap[name];
      if (!mapped) continue;
      const code = asStr(it.resultCode) ?? asStr(it.resultCodeType);
      const rawResult = asStr(it.result);
      const status = normalizeBodyStatus((code ? codeMap[code] : null) ?? rawResult ?? "Оригинал");
      rows.push({ part: mapped.part, status, section: mapped.section });
    }
  }
  const uniq = new Map<string, BodyPanelRow>();
  for (const r of rows) {
    const k = r.part.trim().toLowerCase();
    const prev = uniq.get(k);
    if (!prev || bodyStatusWeight(r.status) > bodyStatusWeight(prev.status)) {
      uniq.set(k, { part: r.part, status: normalizeBodyStatus(r.status), section: r.section });
    }
  }
  const out = Array.from(uniq.values());
  const external = out.filter((r) => r.section === "external" || (r.section == null && !isInternalBodyPart(r.part)));
  const internal = out.filter((r) => r.section === "internal" || (r.section == null && isInternalBodyPart(r.part)));
  return {
    internal: withOriginalDefaults(internal, "internal"),
    external: withOriginalDefaults(external, "external"),
  };
}
