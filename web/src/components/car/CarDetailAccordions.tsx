"use client";

import { useEffect, useMemo, useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { Badge } from "@/components/ui/badge";
import {
  asStr,
  cleanScalarText,
  diagnosisStatusTone,
  buildNormalizedCarTitle,
  formatHumanDate,
  formatInspectionListItem,
  formatKm,
  formatKrw,
  normalizeFuelLabel,
  formatRubFromUnknown,
  formatRegYearMonth,
  getPath,
  joinUniqueSpecs,
  prettifyDataKey,
  toneClass,
  translateKoToRuText,
} from "@/lib/car-detail-data";
import {
  collectSelectedEncarOptions,
  displayEncarStandardOption,
} from "@/lib/encar-options-display";
import { localizeDongchediOptionText } from "@/lib/dongchedi-option-ru-table";
import { formatPriceLabel } from "@/lib/format-price";

const SWITCH_BAR_CLASS = "inline-flex w-full rounded-xl border border-border/60 bg-muted/20 p-1.5";
const SWITCH_BUTTON_CLASS =
  "flex-1 rounded-lg px-3.5 py-2 text-sm font-medium leading-none transition";

function localizeLabel(label: string): string {
  return translateKoToRuText(prettifyDataKey(label));
}

function localizeValue(value: string): string {
  const cleaned = cleanScalarText(value);
  if (!cleaned) return "Не указано";
  const t = translateKoToRuText(cleaned);
  if (t === "[]") return "Не выявлены";
  if (t === "{}") return "Нет данных";
  return t;
}

function SpecGrid({ rows }: { rows: { label: string; value: string }[] }) {
  const filtered = rows
    .map((r) => ({ label: r.label, value: cleanScalarText(r.value) ?? "" }))
    .filter((r) => r.value.trim());
  if (!filtered.length) {
    return <p className="text-sm text-muted-foreground">Нет данных.</p>;
  }
  return (
    <dl className="grid grid-cols-1 gap-2.5 md:grid-cols-2 md:gap-3">
      {filtered.map((r, idx) => (
        <div
          key={`${r.label}-${idx}`}
          className="rounded-2xl border border-border/45 bg-muted/15 px-3 py-2.5 transition-colors hover:bg-muted/25 md:grid md:grid-cols-[minmax(0,42%)_minmax(0,1fr)] md:gap-3 md:px-3.5 md:py-3"
        >
          <dt className="text-[11px] font-semibold tracking-wide text-muted-foreground md:pt-0.5">
            {localizeLabel(r.label)}
          </dt>
          <dd className="mt-1 text-sm font-medium leading-snug [overflow-wrap:anywhere] text-foreground md:mt-0">
            {localizeValue(r.value)}
          </dd>
        </div>
      ))}
    </dl>
  );
}

function normalizeBodyStatus(raw: string): string {
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

function bodyStatusColor(text: string): string {
  const t = normalizeBodyStatus(text).toLowerCase();
  if (t.includes("ориг")) return "bg-emerald-100 text-emerald-900 border-emerald-300";
  if (t.includes("окрас") || t.includes("ремонт") || t.includes("царап")) return "bg-amber-100 text-amber-900 border-amber-300";
  if (t.includes("свар") || t.includes("замен") || t.includes("дтп")) return "bg-red-100 text-red-900 border-red-300";
  if (t.includes("вмят") || t.includes("повреж") || t.includes("корроз")) return "bg-orange-100 text-orange-900 border-orange-300";
  return "bg-slate-100 text-slate-800 border-slate-300";
}

function isNegativeFlag(v: unknown): boolean {
  const raw = String(v ?? "").trim();
  if (!raw) return true;
  const s = translateKoToRuText(raw).trim().toLowerCase();
  return ["нет", "없음", "no", "normal", "0", "false", "n"].includes(s);
}

type BodyRow = { part: string; status: string; section?: "external" | "internal" };

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
  ];
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

function withOriginalDefaults(rows: BodyRow[], section: "external" | "internal"): BodyRow[] {
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

function hasStructuredBodyPayload(
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

function collectBodyRows({
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
}): { external: BodyRow[]; internal: BodyRow[] } {
  const rows: BodyRow[] = [];
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
      if (part && status) rows.push({ part, status });
    }
  }
  if (bodyChanged && typeof bodyChanged === "object" && !Array.isArray(bodyChanged)) {
    for (const [k, v] of Object.entries(bodyChanged as Record<string, unknown>)) {
      const part = translateKoToRuText(k);
      const status = normalizeBodyStatus(asStr(v) ?? "Замена");
      if (part && status) rows.push({ part, status });
    }
  }
  if (Array.isArray(paintPartTypes)) {
    for (const x of paintPartTypes) {
      const part = translateKoToRuText(typeof x === "object" ? formatInspectionListItem(x) : String(x));
      if (part) rows.push({ part, status: "Окрас" });
    }
  }
  if (Array.isArray(seriousTypes)) {
    for (const x of seriousTypes) {
      const part = translateKoToRuText(typeof x === "object" ? formatInspectionListItem(x) : String(x));
      if (part) rows.push({ part, status: "Повреждение" });
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
  const uniq = new Map<string, BodyRow>();
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

function BodyConditionSection({
  outers,
  bodyPanels,
  bodyChanged,
  paintPartTypes,
  seriousTypes,
  diagnosisItems,
  accident,
  simpleRepair,
}: {
  outers: unknown;
  bodyPanels: unknown;
  bodyChanged: unknown;
  paintPartTypes: unknown;
  seriousTypes: unknown;
  diagnosisItems: unknown;
  accident: unknown;
  simpleRepair: unknown;
}) {
  const reduceMotion = useReducedMotion();
  const hasStructured = useMemo(
    () =>
      hasStructuredBodyPayload(
        bodyPanels,
        outers,
        bodyChanged,
        paintPartTypes,
        seriousTypes,
        diagnosisItems,
      ),
    [bodyPanels, outers, bodyChanged, paintPartTypes, seriousTypes, diagnosisItems],
  );
  const encarCosmetic = !isNegativeFlag(simpleRepair);
  const encarAccident = !isNegativeFlag(accident);
  const hasEncarSummary = encarCosmetic || encarAccident;

  const groups = useMemo(
    () => collectBodyRows({ outers, bodyPanels, bodyChanged, paintPartTypes, seriousTypes, diagnosisItems }),
    [outers, bodyPanels, bodyChanged, paintPartTypes, seriousTypes, diagnosisItems],
  );

  const tabs = [
    { key: "external" as const, title: "Внешние элементы", rows: groups.external },
    { key: "internal" as const, title: "Внутренние элементы", rows: groups.internal },
  ];
  const [activeTab, setActiveTab] = useState<"external" | "internal">("external");
  useEffect(() => {
    if (!tabs.length) return;
    if (!tabs.some((x) => x.key === activeTab)) setActiveTab(tabs[0].key);
  }, [tabs, activeTab]);
  const activeRows = tabs.find((x) => x.key === activeTab)?.rows ?? [];

  if (!hasStructured && !hasEncarSummary) {
    return (
      <p className="text-sm text-muted-foreground">
        Нет данных инспекции кузова по этому объявлению.
      </p>
    );
  }

  if (!tabs.some((t) => t.rows.length > 0)) {
    return <p className="text-sm text-muted-foreground">Повреждений не зафиксировано, элементы кузова в исходном состоянии.</p>;
  }
  return (
    <div className="space-y-3">
      {hasEncarSummary ? (
        <div className="rounded-xl border border-amber-200/90 bg-amber-50/95 px-3 py-2.5 text-xs leading-snug text-amber-950 dark:border-amber-900/55 dark:bg-amber-950/35 dark:text-amber-50">
          <ul className="list-disc space-y-1 ps-4 [overflow-wrap:anywhere]">
            {encarCosmetic ? (
              <li>
                По сводке Encar отмечен косметический ремонт. Ниже — типовая сетка панелей; без детализации в
                данных статусы показаны как «Оригинал», если нет точечных отметок.
              </li>
            ) : null}
            {encarAccident ? (
              <li>
                По сводке Encar отмечены следы ДТП / силовые элементы. Проверьте также блок страховой истории и
                диагностику.
              </li>
            ) : null}
          </ul>
        </div>
      ) : null}
      <div className={SWITCH_BAR_CLASS}>
        {tabs.map((tab) => (
          <button
            key={tab.key}
            type="button"
            onClick={() => setActiveTab(tab.key)}
            className={`${SWITCH_BUTTON_CLASS} ${
              activeTab === tab.key ? "bg-background shadow-sm text-foreground" : "text-muted-foreground hover:text-foreground"
            }`}
          >
            {tab.title}
          </button>
        ))}
      </div>
      <AnimatePresence mode="wait" initial={false}>
        <motion.div
          key={activeTab}
          layout
          initial={reduceMotion ? false : { opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          exit={reduceMotion ? undefined : { opacity: 0, y: -4 }}
          transition={{ duration: reduceMotion ? 0 : 0.2, ease: "easeOut" }}
          className="overflow-hidden"
        >
          {activeRows.length ? (
            <ul className="grid grid-cols-1 gap-2 md:grid-cols-2">
              {activeRows.map((r, i) => (
                <li key={`${activeTab}-${r.part}-${i}`} className="flex items-center justify-between gap-2 rounded-xl border border-border/50 px-3 py-2">
                  <span className="text-sm">{r.part}</span>
                  <span className={`rounded-full border px-2.5 py-1 text-xs font-medium ${bodyStatusColor(r.status)}`}>{r.status}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="rounded-xl border border-border/45 bg-muted/10 px-3 py-2 text-sm text-muted-foreground">
              По разделу «{activeTab === "internal" ? "Внутренние элементы" : "Внешние элементы"}» изменений не зафиксировано.
            </p>
          )}
        </motion.div>
      </AnimatePresence>
    </div>
  );
}

function parseJson(v: unknown): unknown {
  if (typeof v !== "string") return v;
  try {
    return JSON.parse(v) as unknown;
  } catch {
    return null;
  }
}

function collectDongchediRecommendedFallback(d: Record<string, unknown>): string[] {
  const raw = d.high_light_config;
  if (!Array.isArray(raw)) return [];
  const seen = new Set<string>();
  const out: string[] = [];
  for (const entry of raw) {
    if (!entry || typeof entry !== "object") continue;
    const item = entry as Record<string, unknown>;
    const candidate = asStr(item.name) ?? asStr(item.title) ?? asStr(item.value);
    if (!candidate) continue;
    const ru = localizeDongchediOptionText(candidate);
    if (!ru || seen.has(ru)) continue;
    seen.add(ru);
    out.push(ru);
  }
  return out;
}

function AccidentCases({
  items,
  title,
  krwRate,
}: {
  items: unknown[];
  title: string;
  krwRate: number;
}) {
  const list = items
    .map((x) => (x && typeof x === "object" ? (x as Record<string, unknown>) : null))
    .filter((x): x is Record<string, unknown> => Boolean(x));
  if (!list.length) return null;
  return (
    <div>
      <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        {title}
      </h4>
      <ul className="space-y-2.5">
        {list.map((a, i) => {
          const date = formatHumanDate(a.date) ?? cleanScalarText(a.date);
          const partCost = Number(a.partCost ?? 0);
          const laborCost = Number(a.laborCost ?? 0);
          const paintCost = Number(a.paintingCost ?? 0);
          const hasBodyWork = Number.isFinite(partCost + laborCost + paintCost) && partCost + laborCost + paintCost > 0;
          const kind = hasBodyWork ? "Кузовной/ремонтный случай" : "Технический/гарантийный случай";
          const rubOrNone = (v: unknown): string => {
            const n = typeof v === "number" ? v : Number(String(v ?? "").replace(/\s/g, ""));
            if (!Number.isFinite(n) || n <= 0) return "Нет";
            return formatPriceLabel(n * krwRate);
          };
          const part = rubOrNone(a.partCost);
          const labor = rubOrNone(a.laborCost);
          const paint = rubOrNone(a.paintingCost);
          const payout = rubOrNone(a.insuranceBenefit);
          return (
            <li key={i} className="rounded-xl border border-border/50 bg-muted/15 p-3">
              <div className="mb-2 flex flex-wrap items-center gap-2">
                {date ? <Badge variant="secondary">{date}</Badge> : null}
                <Badge variant="outline">{kind}</Badge>
              </div>
              <div className="grid grid-cols-1 gap-2 text-sm md:grid-cols-2">
                <p><span className="text-muted-foreground">Запчасти:</span> {part}</p>
                <p><span className="text-muted-foreground">Работы:</span> {labor}</p>
                <p><span className="text-muted-foreground">Покраска:</span> {paint}</p>
                <p><span className="text-muted-foreground">Страховая выплата:</span> {payout}</p>
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

function RecordOpenSection({ ro }: { ro: Record<string, unknown> }) {
  const reduceMotion = useReducedMotion();
  const [krwRate, setKrwRate] = useState<number | null>(null);
  const krwRubRateSafe = krwRate && Number.isFinite(krwRate) && krwRate > 0 ? krwRate : 0.0539;
  useEffect(() => {
    let cancelled = false;
    const run = async () => {
      try {
        const r = await fetch(`/api/cbr-rates?ts=${Date.now()}`, { cache: "no-store" });
        if (!r.ok) return;
        const d = (await r.json()) as { valute?: Record<string, { Value: number; Nominal: number }> };
        const val = d?.valute?.KRW;
        if (!val || !Number.isFinite(val.Value) || !Number.isFinite(val.Nominal) || val.Nominal <= 0) return;
        const rate = val.Value / val.Nominal;
        if (!cancelled) setKrwRate(rate);
      } catch {
        // ignore
      }
    };
    void run();
    return () => {
      cancelled = true;
    };
  }, []);

  const num = (v: unknown): number | null => {
    if (v == null || v === "") return null;
    const n = typeof v === "number" ? v : Number(String(v).replace(/\s/g, ""));
    return Number.isFinite(n) ? n : null;
  };
  const rubFromKrw = (v: unknown): string | null => {
    const n = num(v);
    if (n == null) return null;
    return formatPriceLabel(n * krwRubRateSafe);
  };

  const rows: { label: string; value: string }[] = [];
  const add = (label: string, v: unknown, fmt?: (x: unknown) => string | null) => {
    const s = fmt ? fmt(v) : asStr(v);
    if (s) rows.push({ label, value: s });
  };
  const asCount = (v: unknown): number => {
    const n = typeof v === "number" ? v : Number(String(v ?? "").replace(/\s/g, ""));
    return Number.isFinite(n) ? Math.max(0, Math.trunc(n)) : 0;
  };
  const myAccCnt = asCount(ro.myAccidentCnt);
  const totalLossCnt = asCount(ro.totalLossCnt);
  const floodTotalCnt = asCount(ro.floodTotalLossCnt);
  const floodPartCnt = asCount(ro.floodPartLossCnt);
  const theftCnt = asCount(ro.robberCnt);

  add("ДТП по текущему авто", String(myAccCnt));
  add("Сумма страховых выплат по текущему авто", ro.myAccidentCost, (v) => {
    const n = asCount(v);
    if (n <= 0) return "Нет";
    return rubFromKrw(v);
  });
  add("Конструктивная гибель", totalLossCnt > 0 ? `Да (${totalLossCnt})` : "Нет");
  add(
    "Затопления",
    floodTotalCnt > 0 || floodPartCnt > 0
      ? `Тотал: ${floodTotalCnt}, частичное: ${floodPartCnt}`
      : "Нет",
  );
  add("Угон", theftCnt > 0 ? `Да, случаев: ${theftCnt}` : "Нет");
  add("Отзывные кампании", ro.recall, (v) => {
    const t = translateKoToRuText(String(v ?? "")).trim();
    if (!t || t === "0" || t.toLowerCase() === "none") return "Нет";
    return t;
  });
  add("Статус выполнения отзывных кампаний", ro.recallFullFillTypes, (v) => {
    const t = translateKoToRuText(String(v ?? "")).trim();
    if (!t || t === "0" || t.toLowerCase() === "none") return "Нет данных";
    return t;
  });

  const accidents = ro.accidents;
  const ownerChanges = ro.ownerChanges;
  const ownersCount = Array.isArray(ownerChanges) ? ownerChanges.length : Number(ro.ownerChangeCnt ?? 0);
  const mineCases = Array.isArray(accidents)
    ? accidents.filter((x) => x && typeof x === "object" && String((x as Record<string, unknown>).type ?? "").trim() !== "2")
    : [];
  const otherCases = Array.isArray(accidents)
    ? accidents.filter((x) => x && typeof x === "object" && String((x as Record<string, unknown>).type ?? "").trim() === "2")
    : [];
  const hasOtherCases = otherCases.length > 0;
  const [insuranceTab, setInsuranceTab] = useState<"mine" | "other">("mine");
  useEffect(() => {
    if (!hasOtherCases && insuranceTab === "other") setInsuranceTab("mine");
  }, [hasOtherCases, insuranceTab]);

  return (
    <div className="space-y-4">
      <SpecGrid rows={rows} />
      {ownersCount > 0 ? (
        <div className="rounded-xl border border-border/50 bg-muted/10 px-3 py-2">
          <p className="text-xs text-muted-foreground">Собственники</p>
          <p className="text-sm font-medium">Собственников авто в Корее: {ownersCount}</p>
        </div>
      ) : null}
      {Array.isArray(accidents) && accidents.length > 0 ? (
        <div className="space-y-3">
          {hasOtherCases ? (
            <div className={SWITCH_BAR_CLASS}>
              <button
                type="button"
                onClick={() => setInsuranceTab("mine")}
                className={`${SWITCH_BUTTON_CLASS} ${
                  insuranceTab === "mine" ? "bg-background shadow-sm text-foreground" : "text-muted-foreground hover:text-foreground"
                }`}
              >
                По текущему авто
              </button>
              <button
                type="button"
                onClick={() => setInsuranceTab("other")}
                className={`${SWITCH_BUTTON_CLASS} ${
                  insuranceTab === "other" ? "bg-background shadow-sm text-foreground" : "text-muted-foreground hover:text-foreground"
                }`}
              >
                Соучастник(и) ДТП
              </button>
            </div>
          ) : null}
          <AnimatePresence mode="wait" initial={false}>
            <motion.div
              key={insuranceTab}
              layout
              initial={reduceMotion ? false : { opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={reduceMotion ? undefined : { opacity: 0, y: -4 }}
              transition={{ duration: reduceMotion ? 0 : 0.2, ease: "easeOut" }}
              className="overflow-hidden"
            >
              <AccidentCases
                items={insuranceTab === "other" ? otherCases : mineCases}
                title={insuranceTab === "other" ? "Страховые случаи соучастников ДТП" : "Страховые случаи по текущему авто"}
                krwRate={krwRubRateSafe}
              />
            </motion.div>
          </AnimatePresence>
        </div>
      ) : null}
    </div>
  );
}

function EquipmentSection({ d, extra }: { d: Record<string, unknown>; extra: Record<string, unknown> | undefined }) {
  const reduceMotion = useReducedMotion();
  const options = d.options as Record<string, unknown> | undefined;
  const standard = options?.standard;
  const codes = useMemo(() => (Array.isArray(standard) ? standard : []), [standard]);
  const dongchediRecommendedRaw = parseJson(d.dongchedi_recommended_options);
  const dongchediRecommendedFallback = useMemo(() => collectDongchediRecommendedFallback(d), [d]);
  const dongchediRecommended = useMemo(() => {
    if (!Array.isArray(dongchediRecommendedRaw)) return dongchediRecommendedFallback;
    const out: string[] = [];
    const seen = new Set<string>();
    for (const item of dongchediRecommendedRaw) {
      const ru = localizeDongchediOptionText(typeof item === "string" ? item : item != null ? String(item) : "");
      if (!ru || seen.has(ru)) continue;
      seen.add(ru);
      out.push(ru);
    }
    return out.length ? out : dongchediRecommendedFallback;
  }, [dongchediRecommendedRaw, dongchediRecommendedFallback]);

  const sp = getPath(extra, ["sellingpoint"]) as Record<string, unknown> | undefined;
  const uniquePhotos = getPath(sp, ["uniqueOptionPhotos"]);
  const choicePhotos = getPath(sp, ["choiceOptionPhotos"]);
  const selectedOptions = useMemo(
    () => collectSelectedEncarOptions(uniquePhotos, choicePhotos, extra, d),
    [uniquePhotos, choicePhotos, extra, d],
  );
  const selectedLabels = useMemo(() => {
    const seen = new Set<string>();
    const out: string[] = [];
    for (const row of selectedOptions) {
      const lb = cleanScalarText(row.label);
      if (!lb || /^Опция\s+\d+$/i.test(lb) || seen.has(lb)) continue;
      seen.add(lb);
      out.push(lb);
    }
    for (const c of codes) {
      const label = cleanScalarText(displayEncarStandardOption(c, uniquePhotos, choicePhotos, extra, d));
      if (!label || /^Опция\s+\d+$/i.test(label) || seen.has(label)) continue;
      seen.add(label);
      out.push(label);
    }
    return out;
  }, [selectedOptions, codes, uniquePhotos, choicePhotos, extra, d]);
  const staticCodesAll = useMemo(
    () =>
      codes
        .map((c) => cleanScalarText(displayEncarStandardOption(c, uniquePhotos, choicePhotos, extra, d)))
        .filter((x): x is string => Boolean(x)),
    [codes, uniquePhotos, choicePhotos, extra, d],
  );
  const allLabels = useMemo(() => {
    const seen = new Set<string>();
    const out: string[] = [];
    const push = (v: string) => {
      const t = cleanScalarText(v);
      if (!t || /^Опция\s+\d+$/i.test(t) || seen.has(t)) return;
      seen.add(t);
      out.push(t);
    };
    for (const v of dongchediRecommended) push(v);
    for (const v of selectedLabels) push(v);
    for (const v of staticCodesAll) push(v);
    return out;
  }, [dongchediRecommended, selectedLabels, staticCodesAll]);
  const hasAnyRenderedOptions = allLabels.length > 0;

  type OptGroupKey = "assist" | "interior" | "safety" | "comfort" | "media" | "other";
  const grouped = useMemo(() => {
    const buckets: Record<OptGroupKey, string[]> = {
      assist: [],
      interior: [],
      safety: [],
      comfort: [],
      media: [],
      other: [],
    };
    const hasAny = (s: string, kws: string[]) => kws.some((k) => s.includes(k));
    for (const raw of allLabels) {
      const s = raw.toLowerCase();
      if (hasAny(s, ["круиз", "ассист", "удерж", "полос", "автопарков", "парковк", "слеп", "lane", "blind"])) {
        buckets.assist.push(raw);
      } else if (hasAny(s, ["интерьер", "экстерь", "салон", "сиден", "руль", "люк", "панорам", "зеркал", "диск"])) {
        buckets.interior.push(raw);
      } else if (hasAny(s, ["airbag", "подуш", "abs", "esp", "esc", "тормоз", "безопас", "столкнов"])) {
        buckets.safety.push(raw);
      } else if (hasAny(s, ["подогрев", "вентиляц", "климат", "кондиц", "электропривод", "багажник", "память"])) {
        buckets.comfort.push(raw);
      } else if (hasAny(s, ["мультимед", "навигац", "carplay", "android auto", "bluetooth", "аудио", "дисплей", "hud"])) {
        buckets.media.push(raw);
      } else {
        buckets.other.push(raw);
      }
    }
    return buckets;
  }, [allLabels]);
  const groupMetaBase = [
    { key: "assist", title: "Ассистенты" },
    { key: "interior", title: "Интерьер и экстерьер" },
    { key: "safety", title: "Безопасность" },
    { key: "comfort", title: "Комфорт" },
    { key: "media", title: "Мультимедиа" },
    { key: "other", title: "Прочее" },
  ] as const satisfies ReadonlyArray<{ key: OptGroupKey; title: string }>;
  const groupMeta = groupMetaBase.filter((g) => grouped[g.key].length > 0);
  const [activeGroup, setActiveGroup] = useState<OptGroupKey>("assist");
  useEffect(() => {
    if (!groupMeta.length) return;
    if (!groupMeta.some((g) => g.key === activeGroup)) setActiveGroup(groupMeta[0].key);
  }, [groupMeta, activeGroup]);
  const activeItems = grouped[activeGroup] ?? [];

  return (
    <div className="space-y-5">
      {!hasAnyRenderedOptions ? (
        <p className="text-sm text-muted-foreground">По этой карточке опции не распознаны.</p>
      ) : (
        <div className="space-y-3">
          {groupMeta.length > 1 ? (
            <div className={SWITCH_BAR_CLASS}>
              {groupMeta.map((g) => (
                <button
                  key={g.key}
                  type="button"
                  onClick={() => setActiveGroup(g.key)}
                  className={`${SWITCH_BUTTON_CLASS} ${
                    activeGroup === g.key ? "bg-background shadow-sm text-foreground" : "text-muted-foreground hover:text-foreground"
                  }`}
                >
                  {g.title}
                </button>
              ))}
            </div>
          ) : null}
          <AnimatePresence mode="wait" initial={false}>
            <motion.div
              key={activeGroup}
              layout
              initial={reduceMotion ? false : { opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={reduceMotion ? undefined : { opacity: 0, y: -4 }}
              transition={{ duration: reduceMotion ? 0 : 0.2, ease: "easeOut" }}
              className="overflow-hidden"
            >
              <ul className="grid grid-cols-1 gap-2 md:grid-cols-2">
                {activeItems.map((label, i) => (
                  <li key={`${activeGroup}-${i}`} className="rounded-xl border border-border/55 bg-background px-3 py-2 text-xs leading-snug">
                    {label}
                  </li>
                ))}
              </ul>
            </motion.div>
          </AnimatePresence>
        </div>
      )}
    </div>
  );
}

function normalizeDiagLabel(raw: string): string {
  const t = raw.toLowerCase();
  if (t.includes("водяной насос")) return "Насос системы охлаждения";
  if (t.includes("common rail")) return raw.replace(/\s*\(common rail\)\s*/gi, "");
  return raw;
}

function normalizeDiagValue(raw: string): string {
  const t = raw.trim().toLowerCase();
  if (t === "нет") return "В норме";
  return raw;
}

export function CarDetailAccordions({
  data,
  diagnosisPhotosCount,
}: {
  data: Record<string, unknown>;
  diagnosisPhotosCount: number;
}) {
  const reduceMotion = useReducedMotion();
  void diagnosisPhotosCount;
  const extra =
    data.extra && typeof data.extra === "object" && !Array.isArray(data.extra)
      ? (data.extra as Record<string, unknown>)
      : undefined;

  const inspectionRaw = parseJson(getPath(extra, ["inspection"]));
  const inspection =
    inspectionRaw && typeof inspectionRaw === "object" && !Array.isArray(inspectionRaw)
      ? (inspectionRaw as Record<string, unknown>)
      : undefined;
  const masterRaw = parseJson(inspection?.master);
  const master =
    masterRaw && typeof masterRaw === "object" && !Array.isArray(masterRaw)
      ? (masterRaw as Record<string, unknown>)
      : undefined;
  const detail = getPath(master, ["detail"]) as Record<string, unknown> | undefined;

  const mileage =
    formatKm(data.km_age) ??
    formatKm(getPath(detail, ["mileage"])) ??
    formatKm(getPath(extra, ["inspection", "master", "detail", "mileage"]));

  const vin = asStr(data.vin) ?? asStr(getPath(detail, ["vin"]));

  const power =
    asStr((data as Record<string, unknown>).power_kwhp) ??
    asStr(data.power) ??
    asStr(data.hp);

  const generalRows: { label: string; value: string }[] = [];
  const push = (label: string, v: string | null) => {
    if (v) generalRows.push({ label, value: v });
  };

  push(
    "Наименование",
    buildNormalizedCarTitle(
      data.mark,
      data.model,
      data.generation ?? data.configuration ?? data.gradeName,
      data.source,
    ) ??
      joinUniqueSpecs(data.mark, data.model, data.generation),
  );
  push("Год / месяц", formatRegYearMonth(data.yearMonth) ?? formatRegYearMonth(data.year));
  push("Цвет", asStr(data.color));
  push("Пробег", mileage);
  push("VIN", vin);
  push(
    "Двигатель / объём",
    [normalizeFuelLabel(data.engine_type), asStr(data.displacement)].filter(Boolean).join(", ") || null,
  );
  push("КПП / привод", [asStr(data.transmission_type), asStr(data.drive_type)].filter(Boolean).join(", ") || null);
  push("Мощность", power);
  push("Места", asStr(data.seatCount));

  const paintPartTypes = detail?.paintPartTypes ?? getPath(detail, ["paintPartTypes"]);
  const seriousTypes = detail?.seriousTypes ?? getPath(detail, ["seriousTypes"]);

  const outers = inspection?.outers;

  const accident = master?.accdient ?? master?.accident;
  const simpleRepair = master?.simpleRepair;
  const bodyChanged =
    getPath(extra, ["inspection_structured", "bodyChanged"]) ?? getPath(master, ["bodyChanged"]);
  const inspectionStructuredRaw = parseJson(getPath(extra, ["inspection_structured"]));
  const inspectionStructured =
    inspectionStructuredRaw && typeof inspectionStructuredRaw === "object" && !Array.isArray(inspectionStructuredRaw)
      ? (inspectionStructuredRaw as Record<string, unknown>)
      : undefined;
  const bodyPanels = getPath(inspectionStructured, ["bodyPanels"]);
  const diagnosisRaw = parseJson(getPath(extra, ["diagnosis"]));
  const diagnosis =
    diagnosisRaw && typeof diagnosisRaw === "object" && !Array.isArray(diagnosisRaw)
      ? (diagnosisRaw as Record<string, unknown>)
      : undefined;
  const diagnosisItems = getPath(diagnosis, ["items"]);

  const structured = inspectionStructured;

  const engineTransmission = structured?.engineTransmission as Record<string, unknown> | undefined;
  const chassis = structured?.chassis as Record<string, unknown> | undefined;
  const electrical = structured?.electrical as Record<string, unknown> | undefined;
  const additional = structured?.additional as Record<string, unknown> | undefined;

  const recordOpen =
    extra?.record_open && typeof extra.record_open === "object"
      ? (extra.record_open as Record<string, unknown>)
      : undefined;

  const defaultOpen = ["general"];

  const toStructuredRows = (obj: Record<string, unknown> | undefined): Array<{ label: string; value: string }> => {
    if (!obj) return [];
    return Object.entries(obj)
      .map(([k, v]) => {
        const base = asStr(v)
          ? translateKoToRuText(asStr(v)!)
          : typeof v === "object"
            ? translateKoToRuText(JSON.stringify(v))
            : "";
        const cleaned = cleanScalarText(base);
        if (!cleaned) return null;
        const ruLabel = normalizeDiagLabel(translateKoToRuText(prettifyDataKey(k)));
        const ruValue = normalizeDiagValue(translateKoToRuText(cleaned));
        return { label: ruLabel, value: ruValue };
      })
      .filter((x): x is { label: string; value: string } => Boolean(x));
  };

  const diagSections = [
    { key: "engine", label: "Двигатель", rows: toStructuredRows(engineTransmission) },
    { key: "chassis", label: "Ходовая и тормоза", rows: toStructuredRows(chassis) },
    { key: "electrical", label: "Электрика", rows: toStructuredRows(electrical) },
    { key: "additional", label: "Дополнительно", rows: toStructuredRows(additional) },
  ].filter((x) => x.rows.length > 0);
  const [activeDiagTab, setActiveDiagTab] = useState<string>(diagSections[0]?.key ?? "engine");
  const activeDiag = diagSections.find((x) => x.key === activeDiagTab) ?? diagSections[0];
  useEffect(() => {
    if (!diagSections.length) return;
    if (!diagSections.some((x) => x.key === activeDiagTab)) {
      setActiveDiagTab(diagSections[0].key);
    }
  }, [diagSections, activeDiagTab]);

  return (
    <Accordion
      type="multiple"
      defaultValue={defaultOpen}
      className="mt-6 max-w-full overflow-hidden rounded-2xl border border-border/70 bg-card shadow-sm ring-1 ring-black/[0.04] dark:ring-white/[0.07] sm:rounded-3xl"
    >
      <AccordionItem value="general" className="first:rounded-t-3xl">
        <AccordionTrigger className="break-words py-4 ps-4 pe-10 text-start text-base font-semibold tracking-tight [overflow-wrap:anywhere] hover:bg-muted/30 hover:no-underline sm:ps-5 sm:pe-12">
          Общая информация
        </AccordionTrigger>
        <AccordionContent className="px-4 sm:px-5">
          <SpecGrid rows={generalRows} />
        </AccordionContent>
      </AccordionItem>

      <AccordionItem value="equipment">
        <AccordionTrigger className="break-words py-4 ps-4 pe-10 text-start text-base font-semibold tracking-tight [overflow-wrap:anywhere] hover:bg-muted/30 hover:no-underline sm:ps-5 sm:pe-12">
          Комплектация
        </AccordionTrigger>
        <AccordionContent className="px-4 sm:px-5">
          <EquipmentSection d={data} extra={extra} />
        </AccordionContent>
      </AccordionItem>

      <AccordionItem value="body">
        <AccordionTrigger className="break-words py-4 ps-4 pe-10 text-start text-base font-semibold tracking-tight [overflow-wrap:anywhere] hover:bg-muted/30 hover:no-underline sm:ps-5 sm:pe-12">
          Состояние кузова
        </AccordionTrigger>
        <AccordionContent className="px-4 sm:px-5">
          <div className="space-y-4">
            <BodyConditionSection
              outers={outers}
              bodyPanels={bodyPanels}
              bodyChanged={bodyChanged}
              paintPartTypes={paintPartTypes}
              seriousTypes={seriousTypes}
              diagnosisItems={diagnosisItems}
              accident={accident}
              simpleRepair={simpleRepair}
            />
          </div>
        </AccordionContent>
      </AccordionItem>

      <AccordionItem value="diagnosis">
        <AccordionTrigger className="break-words py-4 ps-4 pe-10 text-start text-base font-semibold tracking-tight [overflow-wrap:anywhere] hover:bg-muted/30 hover:no-underline sm:ps-5 sm:pe-12">
          Диагностика и техсостояние
        </AccordionTrigger>
        <AccordionContent className="px-4 sm:px-5">
          <div className="space-y-5">
            {diagSections.length > 0 ? (
              <div className="space-y-3">
                <div className={SWITCH_BAR_CLASS}>
                  {diagSections.map((section) => (
                    <button
                      key={section.key}
                      type="button"
                      onClick={() => setActiveDiagTab(section.key)}
                      className={`${SWITCH_BUTTON_CLASS} ${
                        activeDiag?.key === section.key
                          ? "bg-background shadow-sm text-foreground"
                          : "text-muted-foreground hover:text-foreground"
                      }`}
                    >
                      {section.label}
                    </button>
                  ))}
                </div>
                <AnimatePresence mode="wait" initial={false}>
                  {activeDiag ? (
                    <motion.div
                      key={activeDiag.key}
                      layout
                      initial={reduceMotion ? false : { opacity: 0, y: 6 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={reduceMotion ? undefined : { opacity: 0, y: -4 }}
                      transition={{ duration: reduceMotion ? 0 : 0.2, ease: "easeOut" }}
                      className="overflow-hidden"
                    >
                      <ul className="grid grid-cols-1 gap-2 md:grid-cols-2">
                        {activeDiag.rows.map((row) => (
                          <li key={`${activeDiag.key}-${row.label}`} className="rounded-lg border border-border/45 bg-background px-2.5 py-2">
                            <p className="text-xs text-muted-foreground">{row.label}</p>
                            <p className="mt-1 text-sm font-medium">{row.value}</p>
                          </li>
                        ))}
                      </ul>
                    </motion.div>
                  ) : null}
                </AnimatePresence>
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">Подробная карта диагностики в источнике недоступна. Показываем подтвержденные данные из отчета.</p>
            )}
          </div>
        </AccordionContent>
      </AccordionItem>

      <AccordionItem value="insurance">
        <AccordionTrigger className="break-words py-4 ps-4 pe-10 text-start text-base font-semibold tracking-tight [overflow-wrap:anywhere] hover:bg-muted/30 hover:no-underline sm:ps-5 sm:pe-12">
          Страховые случаи и история
        </AccordionTrigger>
        <AccordionContent className="px-4 sm:px-5">
          {recordOpen && Object.keys(recordOpen).length > 0 ? (
            <RecordOpenSection ro={recordOpen} />
          ) : (
            <p className="text-sm text-muted-foreground">Страховая история в источнике не опубликована. По запросу менеджер уточнит данные у продавца.</p>
          )}
        </AccordionContent>
      </AccordionItem>

    </Accordion>
  );
}
